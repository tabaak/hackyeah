import { createContext, use, useEffect, useRef, useState, type ReactNode } from 'react'
import type { CompanyDraft, PendingDoc } from '../components/CompanySetup'
import { api, ApiError, supabase } from './api'
import { makePost, seedPosts, type Company, type Doc, type Post, type PostStatus } from './mock'

export type User = { name: string; email: string; role: 'analyst' | 'compliance' }

const POLL_MS = 3000 // while any document is processing (indexing + AI summary)

function uploadDocs(companyId: string, docs: PendingDoc[]) {
  const form = new FormData()
  docs.forEach(({ file, classification }) => { form.append('files', file); form.append('classifications', classification) })
  return api<Doc[]>(`/companies/${companyId}/documents`, { method: 'POST', body: form })
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
  addCompany: (draft: CompanyDraft, docs: PendingDoc[]) => Promise<void>
  uploadDocuments: (companyId: string, docs: PendingDoc[]) => Promise<void>
  posts: Post[]
  setPostStatus: (id: string, s: PostStatus) => void
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
  const sessionRevision = useRef(0)
  const [companies, setCompanies] = useState<Company[]>([])
  const [posts, setPosts] = useState<Post[]>([])
  // Older builds stored 'dark'; anything unknown falls back to graphite
  const [theme, setTheme] = useState<Theme>(() => {
    const t = load<string>('pg.theme', 'graphite')
    return (THEMES as readonly string[]).includes(t) ? (t as Theme) : 'graphite'
  })

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (stopped) return
      if (!session) {
        sessionRevision.current++
        account.current = null
        clearTimeout(timer)
        controller?.abort()
        setUser(null)
        setCompanies([])
        setPosts([])
        setSessionError(null)
        return
      }

      const id = session.user.id
      if (account.current === id && user !== undefined) return

      account.current = id
      const revision = ++sessionRevision.current
      clearTimeout(timer)
      controller?.abort()
      controller = new AbortController()
      const { signal } = controller
      setUser(undefined)
      setCompanies([])
      setPosts([])
      setSessionError(null)

      // Defer Supabase calls out of its synchronous auth callback to avoid its session lock.
      timer = setTimeout(() => {
        Promise.all([
          api<User>('/me', { signal }),
          api<Company[]>('/companies', { signal }),
        ]).then(([profile, cs]) => {
          if (stopped || revision !== sessionRevision.current) return
          setCompanies(cs)
          setPosts(p => (p.length ? p : cs.flatMap(seedPosts)))
          setAuthError(null)
          setUser(profile)
        }).catch((e: unknown) => {
          if (stopped || signal.aborted || revision !== sessionRevision.current) return
          if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
            setAuthError(e.message)
            setUser(null)
            void supabase.auth.signOut()
          } else {
            setSessionError('Your workspace could not be loaded. Please try again.')
          }
        })
      }, 0)
    })
    return () => {
      stopped = true
      clearTimeout(timer)
      controller?.abort()
      data.subscription.unsubscribe()
    }
  }, [restoreAttempt])

  // Documents are indexed and summarized in the background: refresh until none is processing.
  useEffect(() => {
    if (!companies.some(c => c.documents.some(d => d.status === 'processing'))) return
    const t = setTimeout(() => api<Company[]>('/companies').then(setCompanies, () => {}), POLL_MS)
    return () => clearTimeout(t)
  }, [companies])

  useEffect(() => {
    save('pg.theme', theme)
    document.documentElement.classList.toggle('dark', theme !== 'light')
    document.documentElement.dataset.theme = theme
  }, [theme])

  // Simulated live feed: a new mention every 15 s
  useEffect(() => {
    if (!user || companies.length === 0) return
    let i = 0
    const t = setInterval(() => {
      const c = companies[i % companies.length]
      setPosts(p => [makePost(c, (i * 7 + 3) % 10), ...p].slice(0, 200))
      i++
    }, 15_000)
    return () => clearInterval(t)
  }, [user, companies])

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
      void supabase.auth.signOut()
      setUser(null)
      setCompanies([])
      setPosts([])
      setSessionError(null)
      setAuthError(null)
    },
    companies,
    addCompany: async (draft, docs) => {
      const c = await api<Company>('/companies', { method: 'POST', body: JSON.stringify(draft) })
      let uploadError: Error | null = null
      if (docs.length) c.documents = await uploadDocs(c.id, docs).catch((e: Error) => { uploadError = e; return [] })
      setCompanies(cs => [...cs, c])
      setPosts(p => [...seedPosts(c), ...p].sort((a, b) => b.at - a.at))
      // The company exists now; retrying the wizard would create a duplicate, so point to the card instead.
      if (uploadError) throw new Error(`${c.name} was added, but its documents were not uploaded (${(uploadError as Error).message}). Close this and use Add on the company card.`)
    },
    uploadDocuments: async (companyId, docs) => {
      const added = await uploadDocs(companyId, docs)
      setCompanies(cs => cs.map(c => (c.id === companyId ? { ...c, documents: [...c.documents, ...added] } : c)))
    },
    posts,
    setPostStatus: (id, s) => setPosts(p => p.map(x => (x.id === id ? { ...x, status: s } : x))),
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
