import { createContext, use, useEffect, useRef, useState, type ReactNode } from 'react'
import type { CompanyDraft, PendingDoc } from '../components/CompanySetup'
import { api, ApiError, supabase } from './api'
import { CompanyCreatedError, companyLogoError, uploadCompanyLogo } from './companyLogo'
import { PLATFORM_LABEL, type Company, type Doc, type Post, type PostStatus, type Severity } from './mock'

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
const fetchPosts = (signal?: AbortSignal) => api<Post[]>('/mentions?limit=200', { signal }).then(ps => ps.filter(knownPlatform))
const fetchNotifications = (signal?: AbortSignal) => api<Notifications>('/notifications', { signal })

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
  setCompanyLogo: (companyId: string, file: File | null) => Promise<void>
  posts: Post[]
  setPostStatus: (id: string, s: PostStatus) => void
  refreshFeed: () => Promise<void>
  notifications: Notifications
  markNotificationRead: (id: string) => void
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
  const [notifications, setNotifications] = useState<Notifications>(NO_NOTIFICATIONS)
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
        setPosts([])
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
      setPosts([])
      setNotifications(NO_NOTIFICATIONS)
      setSessionError(null)

      // Defer Supabase calls out of its synchronous auth callback to avoid its session lock.
      timer = setTimeout(() => {
        Promise.all([
          api<User>('/me', { signal }, session.access_token),
          api<Company[]>('/companies', { signal }, session.access_token),
          fetchPosts(signal),
          fetchNotifications(signal),
        ]).then(([profile, cs, ps, ns]) => {
          if (stopped || revision !== sessionRevision.current) return
          hydrated = id
          pending = null
          setCompanies(cs)
          setPosts(ps)
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
    try {
      const [ps, ns] = await Promise.all([fetchPosts(), fetchNotifications()])
      if (account.current !== acct) return // signed out or switched account meanwhile
      setPosts(ps.map(p => (pendingStatus.current.has(p.id) ? { ...p, status: pendingStatus.current.get(p.id)! } : p)))
      setNotifications(ns)
    } catch { /* keep what is shown; the next poll retries */ }
  }
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
      setPosts([])
      setNotifications(NO_NOTIFICATIONS)
      setSessionError(null)
      setAuthError(null)
    },
    companies,
    addCompany: async (draft, docs, logo = null) => {
      const owner = account.current
      const revision = sessionRevision.current
      const token = accessToken.current
      if (!owner || !user || !token) throw new Error('Please sign in before creating a company.')
      const validationError = logo && companyLogoError(logo)
      if (validationError) throw new Error(validationError)
      const c = await api<Company>('/companies', { method: 'POST', body: JSON.stringify(draft) }, token)
      if (owner !== account.current || revision !== sessionRevision.current) throw new Error('Your session changed. Sign in again to reload your companies.')
      const uploadErrors: string[] = []
      await Promise.all([
        logo ? uploadCompanyLogo(c.id, logo, token).then(url => { c.logoUrl = url }).catch((e: Error) => { uploadErrors.push(`Logo: ${e.message}. Click the company avatar to try again.`) }) : undefined,
        docs.length ? uploadDocs(c.id, docs, token).then(d => { c.documents = d }).catch((e: Error) => { uploadErrors.push(`Documents: ${e.message}. Use Add on the company card to try again.`) }) : undefined,
      ])
      if (owner !== account.current || revision !== sessionRevision.current) throw new Error('Your session changed. Sign in again to reload your companies.')
      setCompanies(cs => [...cs, c])
      void refreshFeed() // news for the new company arrive in the background; the poll picks up the rest
      // The company exists now; retrying the wizard would create a duplicate, so point to the card instead.
      if (uploadErrors.length) throw new CompanyCreatedError(uploadErrors.join(' '))
    },
    updateCompany: async (companyId, draft) => {
      const owner = account.current
      const revision = sessionRevision.current
      const token = accessToken.current
      if (!owner || !token) throw new Error('Please sign in before editing a company.')
      const updated = await api<Company>(`/companies/${companyId}`, { method: 'PUT', body: JSON.stringify(draft) }, token)
      if (owner !== account.current || revision !== sessionRevision.current) throw new Error('Your session changed. Sign in again to reload your companies.')
      const { name, website, aliases, sector, country, people, topics } = updated
      setCompanies(cs => cs.map(c => c.id === companyId ? { ...c, name, website, aliases, sector, country, people, topics } : c))
    },
    uploadDocuments: async (companyId, docs) => {
      const owner = account.current
      const revision = sessionRevision.current
      const token = accessToken.current
      if (!owner || !token) throw new Error('Please sign in before uploading documents.')
      const added = await uploadDocs(companyId, docs, token)
      if (owner !== account.current || revision !== sessionRevision.current) return
      setCompanies(cs => cs.map(c => (c.id === companyId ? { ...c, documents: [...c.documents, ...added] } : c)))
    },
    setCompanyLogo: async (companyId, file) => {
      const owner = account.current
      const revision = sessionRevision.current
      const token = accessToken.current
      if (!owner || !token) throw new Error('Please sign in before changing a company logo.')
      let logoUrl: string | null = null
      if (file) {
        logoUrl = await uploadCompanyLogo(companyId, file, token)
      } else {
        await api(`/companies/${companyId}/logo`, { method: 'DELETE' }, token)
      }
      if (owner !== account.current || revision !== sessionRevision.current) return
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
    notifications,
    markNotificationRead: id => {
      setNotifications(n => {
        const item = n.items.find(x => x.id === id)
        if (!item || item.read) return n
        return { items: n.items.map(x => (x.id === id ? { ...x, read: true } : x)), openCount: Math.max(0, n.openCount - 1) }
      })
      void api(`/notifications/${id}/read`, { method: 'PATCH' }).catch(() => {})
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
