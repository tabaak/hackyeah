import { createContext, use, useEffect, useRef, useState, type ReactNode } from 'react'
import { api, ApiError, supabase } from './api'
import { companyLogoError, uploadCompanyLogo } from './companyLogo'
import { CompanyCreatedError, PLATFORM_LABEL, type Company, type CompanyDraft, type Doc, type PendingDoc, type Post, type PostStatus, type Severity } from './domain'

export type User = { name: string; email: string; role: 'analyst' | 'compliance' }

const POLL_MS = 3000 // while any document is processing (indexing + AI summary)
const FEED_POLL_MS = 12_000 // live feed and bell: Endpoints.md recommends polling every 10-15 s

export type AppNotification = {
  id: string
  kind: 'critical_mention' | 'approval_requested' | 'approval_decided'
  mentionId: string | null
  title: string
  severity: Severity
  at: number
  read: boolean
}
type Notifications = { items: AppNotification[]; openCount: number }
const NO_NOTIFICATIONS: Notifications = { items: [], openCount: 0 }

// The API knows more platforms than the UI has icons and labels for; skip those instead of crashing.
const knownPlatform = (p: Post) => p.platform in PLATFORM_LABEL
const PAGE = 200 // the API's maximum page size
type Page = { items: Post[]; full: boolean } // full: there may be older mentions behind this page
const fetchPage = (before?: number, signal?: AbortSignal): Promise<Page> =>
  api<Post[]>(`/mentions?limit=${PAGE}${before ? `&before_timestamp=${before}` : ''}`, { signal })
    .then(ps => ({ items: ps.filter(knownPlatform), full: ps.length >= PAGE }))
const fetchNotifications = (signal?: AbortSignal) => api<Notifications>('/notifications', { signal })

// Desktop alert for high-risk mentions that arrived since the last poll (permission is asked from the bell).
function alertNewCritical(prev: Notifications, next: Notifications) {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  const known = new Set(prev.items.map(n => n.id))
  for (const n of next.items) {
    if (n.kind !== 'critical_mention' || n.read || known.has(n.id)) continue
    const alert = new Notification('High-risk mention', { body: n.title, tag: n.id })
    alert.onclick = () => { window.focus(); location.assign(`/app/feed?respond=${n.mentionId}`) }
  }
}

function uploadDocs(companyId: string, docs: PendingDoc[], token: string) {
  const form = new FormData()
  docs.forEach(({ file, classification }) => { form.append('files', file); form.append('classifications', classification) })
  return api<Doc[]>(`/companies/${companyId}/documents`, { method: 'POST', body: form }, token)
}

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v ? (JSON.parse(v) as T) : fallback
  } catch {
    return fallback
  }
}
function save(key: string, v: unknown) {
  try {
    if (v == null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(v))
  } catch { /* storage unavailable */ }
}

interface Store {
  user: User | null | undefined // undefined while the session is being restored
  authError: string | null
  sessionError: string | null
  retrySession: () => void
  signIn: () => Promise<void>
  signOut: () => void
  companies: Company[]
  addCompany: (draft: CompanyDraft, docs: PendingDoc[], logo?: File | null) => Promise<void>
  updateCompany: (companyId: string, draft: CompanyDraft) => Promise<void>
  uploadDocuments: (companyId: string, docs: PendingDoc[]) => Promise<void>
  deleteDocument: (companyId: string, documentId: string) => Promise<void>
  setCompanyLogo: (companyId: string, file: File | null) => Promise<void>
  posts: Post[]
  setPostStatus: (id: string, s: PostStatus) => void
  refreshFeed: () => Promise<void>
  hasMore: boolean // older mentions can still be loaded
  loadingOlder: boolean
  loadOlder: () => Promise<void>
  notifications: Notifications
  markNotificationRead: (id: string) => void
  markAllNotificationsRead: () => Promise<void>
  theme: Theme
  setTheme: (t: Theme) => void
}

export const THEMES = ['graphite', 'navy', 'laurel', 'light'] as const
export type Theme = (typeof THEMES)[number]

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [authError, setAuthError] = useState<string | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [restoreAttempt, setRestoreAttempt] = useState(0)
  const account = useRef<string | null>(null)
  const accessToken = useRef<string | null>(null)
  const sessionRevision = useRef(0)
  const [companies, setCompanies] = useState<Company[]>([])
  const [posts, setPosts] = useState<Post[]>([])
  const [newestFull, setNewestFull] = useState(false) // the newest page was full, so older mentions may exist
  const [olderDone, setOlderDone] = useState(false) // paging back reached the oldest mention
  const [loadingOlder, setLoadingOlder] = useState(false)
  const resetPosts = () => { setPosts([]); setNewestFull(false); setOlderDone(false) }
  const [notifications, setNotifications] = useState<Notifications>(NO_NOTIFICATIONS)
  const notificationRevision = useRef(0)
  const pendingStatus = useRef(new Map<string, PostStatus>()) // optimistic changes the server has not confirmed yet
  // Older builds stored 'dark'; anything unknown falls back to graphite
  const [theme, setTheme] = useState<Theme>(() => {
    const t = load<string>('pg.theme', 'graphite')
    return (THEMES as readonly string[]).includes(t) ? (t as Theme) : 'graphite'
  })

  useEffect(() => {
    let stopped = false
    let hydrated: string | null = null
    let pending: string | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined
    const initialSessionTimer = setTimeout(() => {
      if (!stopped) setSessionError('Your sign-in session could not be restored. Please try again or sign out.')
    }, 15_000)

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (stopped) return
      clearTimeout(initialSessionTimer)
      accessToken.current = session?.access_token ?? null
      if (!session) {
        sessionRevision.current++
        account.current = null
        hydrated = pending = null
        clearTimeout(timer)
        controller?.abort()
        setUser(null)
        setCompanies([])
        resetPosts()
        setNotifications(NO_NOTIFICATIONS)
        setSessionError(null)
        return
      }

      const id = session.user.id
      if (account.current === id && (hydrated === id || pending === id)) return

      account.current = id
      hydrated = null
      pending = id
      const revision = ++sessionRevision.current
      clearTimeout(timer)
      controller?.abort()
      controller = new AbortController()
      const { signal } = controller
      setUser(undefined)
      setCompanies([])
      resetPosts()
      setNotifications(NO_NOTIFICATIONS)
      setSessionError(null)

      // Defer Supabase calls out of its synchronous auth callback to avoid its session lock.
      timer = setTimeout(() => {
        Promise.all([
          api<User>('/me', { signal }, session.access_token),
          api<Company[]>('/companies', { signal }, session.access_token),
          fetchPage(undefined, signal),
          fetchNotifications(signal),
        ]).then(([profile, cs, page, ns]) => {
          if (stopped || revision !== sessionRevision.current) return
          hydrated = id
          pending = null
          setCompanies(cs)
          setPosts(page.items)
          setNewestFull(page.full)
          setNotifications(ns)
          setAuthError(null)
          setUser(profile)
        }).catch((e: unknown) => {
          if (stopped || signal.aborted || revision !== sessionRevision.current) return
          pending = null
          if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
            setAuthError(e.message)
            setUser(null)
            void supabase.auth.signOut()
          } else {
            setSessionError(e instanceof Error ? e.message : 'Your workspace could not be loaded. Please try again.')
          }
        })
      }, 0)
    })
    return () => {
      stopped = true
      clearTimeout(initialSessionTimer)
      clearTimeout(timer)
      controller?.abort()
      data.subscription.unsubscribe()
    }
  }, [restoreAttempt])

  // Documents are indexed and summarized in the background: refresh until none is processing.
  useEffect(() => {
    if (!companies.some(c => c.documents.some(d => d.status === 'processing'))) return
    const token = accessToken.current
    if (!token) return
    const revision = sessionRevision.current
    const controller = new AbortController()
    const t = setTimeout(() => api<Company[]>('/companies', { signal: controller.signal }, token).then(cs => {
      if (!controller.signal.aborted && revision === sessionRevision.current) setCompanies(cs)
    }, () => {}), POLL_MS)
    return () => { clearTimeout(t); controller.abort() }
  }, [companies])

  useEffect(() => {
    save('pg.theme', theme)
    document.documentElement.classList.toggle('dark', theme !== 'light')
    document.documentElement.dataset.theme = theme
  }, [theme])

  // Live feed and bell: reload from the API while signed in. Statuses the server has not confirmed yet are kept.
  const refreshFeed = async () => {
    const acct = account.current
    if (!acct) return
    const readRevision = notificationRevision.current
    try {
      const [page, ns] = await Promise.all([fetchPage(), fetchNotifications()])
      if (account.current !== acct) return // signed out or switched account meanwhile
      const pending = (p: Post) => (pendingStatus.current.has(p.id) ? { ...p, status: pendingStatus.current.get(p.id)! } : p)
      // The newest page replaces what it covers; older mentions the user already paged back to stay.
      setPosts(prev => {
        const oldest = Math.min(...page.items.map(p => p.at))
        return [...page.items, ...(page.full ? prev.filter(p => p.at < oldest) : [])].map(pending)
      })
      setNewestFull(page.full)
      if (readRevision === notificationRevision.current) {
        alertNewCritical(notifications, ns)
        setNotifications(ns)
      }
    } catch { /* keep what is shown; the next poll retries */ }
  }
  // The signed-in session at call time; `current()` turns false once the user signs out or switches account.
  const session = (action: string) => {
    const owner = account.current
    const revision = sessionRevision.current
    const token = accessToken.current
    if (!owner || !token) throw new Error(`Please sign in before ${action}.`)
    return { token, current: () => owner === account.current && revision === sessionRevision.current }
  }
  const SESSION_CHANGED = 'Your session changed. Sign in again to reload your companies.'

  const refreshRef = useRef(refreshFeed)
  useEffect(() => { refreshRef.current = refreshFeed })

  useEffect(() => {
    if (!user) return
    const t = setInterval(() => { if (!document.hidden) void refreshRef.current() }, FEED_POLL_MS)
    return () => clearInterval(t)
  }, [user])

  const value: Store = {
    user,
    authError,
    sessionError,
    retrySession: () => {
      setSessionError(null)
      setUser(undefined)
      setRestoreAttempt(n => n + 1)
    },
    signIn: async () => {
      setAuthError(null)
      const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })
      if (error) setAuthError(error.message)
    },
    signOut: () => {
      sessionRevision.current++
      account.current = null
      accessToken.current = null
      void supabase.auth.signOut()
      setUser(null)
      setCompanies([])
      resetPosts()
      setNotifications(NO_NOTIFICATIONS)
      setSessionError(null)
      setAuthError(null)
    },
    companies,
    addCompany: async (draft, docs, logo = null) => {
      const { token, current } = session('creating a company')
      const validationError = logo && companyLogoError(logo)
      if (validationError) throw new Error(validationError)
      const c = await api<Company>('/companies', { method: 'POST', body: JSON.stringify(draft) }, token)
      if (!current()) throw new Error(SESSION_CHANGED)
      const uploadErrors: string[] = []
      await Promise.all([
        logo ? uploadCompanyLogo(c.id, logo, token).then(url => { c.logoUrl = url }).catch((e: Error) => { uploadErrors.push(`Logo: ${e.message}. Click the company avatar to try again.`) }) : undefined,
        docs.length ? uploadDocs(c.id, docs, token).then(d => { c.documents = d }).catch((e: Error) => { uploadErrors.push(`Documents: ${e.message}. Use Add on the company card to try again.`) }) : undefined,
      ])
      if (!current()) throw new Error(SESSION_CHANGED)
      setCompanies(cs => [...cs, c])
      void refreshFeed() // news for the new company arrive in the background; the poll picks up the rest
      // The company exists now; retrying the wizard would create a duplicate, so point to the card instead.
      if (uploadErrors.length) throw new CompanyCreatedError(uploadErrors.join(' '))
    },
    updateCompany: async (companyId, draft) => {
      const { token, current } = session('editing a company')
      const updated = await api<Company>(`/companies/${companyId}`, { method: 'PUT', body: JSON.stringify(draft) }, token)
      if (!current()) throw new Error(SESSION_CHANGED)
      const { name, website, aliases, sector, country, people, topics } = updated
      setCompanies(cs => cs.map(c => c.id === companyId ? { ...c, name, website, aliases, sector, country, people, topics } : c))
    },
    uploadDocuments: async (companyId, docs) => {
      const { token, current } = session('uploading documents')
      const added = await uploadDocs(companyId, docs, token)
      if (!current()) return
      setCompanies(cs => cs.map(c => (c.id === companyId ? { ...c, documents: [...c.documents, ...added] } : c)))
    },
    deleteDocument: async (companyId, documentId) => {
      const { token, current } = session('deleting documents')
      await api(`/documents/${documentId}`, { method: 'DELETE' }, token)
      if (!current()) return
      setCompanies(cs => cs.map(c => (c.id === companyId ? { ...c, documents: c.documents.filter(d => d.id !== documentId) } : c)))
    },
    setCompanyLogo: async (companyId, file) => {
      const { token, current } = session('changing a company logo')
      let logoUrl: string | null = null
      if (file) {
        logoUrl = await uploadCompanyLogo(companyId, file, token)
      } else {
        await api(`/companies/${companyId}/logo`, { method: 'DELETE' }, token)
      }
      if (!current()) return
      setCompanies(cs => cs.map(c => c.id === companyId ? { ...c, logoUrl } : c))
    },
    posts,
    setPostStatus: (id, s) => {
      const before = posts.find(p => p.id === id)?.status
      const apply = (status: PostStatus) => setPosts(p => p.map(x => (x.id === id ? { ...x, status } : x)))
      pendingStatus.current.set(id, s)
      apply(s)
      api<Post>(`/mentions/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status: s }) })
        .catch(() => { if (before) apply(before) })
        .finally(() => pendingStatus.current.delete(id))
    },
    refreshFeed,
    hasMore: newestFull && !olderDone,
    loadingOlder,
    loadOlder: async () => {
      const acct = account.current
      const oldest = Math.min(...posts.map(p => p.at))
      if (!acct || loadingOlder || !Number.isFinite(oldest)) return
      setLoadingOlder(true)
      try {
        const page = await fetchPage(oldest)
        if (account.current !== acct) return
        setPosts(prev => { const ids = new Set(prev.map(p => p.id)); return [...prev, ...page.items.filter(p => !ids.has(p.id))] })
        if (!page.full) setOlderDone(true)
      } catch { /* the button stays; try again */ } finally { setLoadingOlder(false) }
    },
    notifications,
    markNotificationRead: id => {
      notificationRevision.current++
      setNotifications(n => {
        const item = n.items.find(x => x.id === id)
        if (!item || item.read) return n
        return { items: n.items.map(x => (x.id === id ? { ...x, read: true } : x)), openCount: Math.max(0, n.openCount - 1) }
      })
      void api(`/notifications/${id}/read`, { method: 'PATCH' }).catch(() => {})
    },
    markAllNotificationsRead: async () => {
      const { token, current } = session('marking notifications as seen')
      await api<void>('/notifications/mark-all-read', { method: 'POST' }, token)
      if (!current()) return
      notificationRevision.current++
      setNotifications(n => ({ items: n.items.map(item => ({ ...item, read: true })), openCount: 0 }))
      void refreshFeed()
    },
    theme,
    setTheme,
  }
  return <Ctx value={value}>{children}</Ctx>
}

export function useStore() {
  const s = use(Ctx)
  if (!s) throw new Error('useStore outside StoreProvider')
  return s
}
