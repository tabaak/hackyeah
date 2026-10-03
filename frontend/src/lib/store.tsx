import { createContext, use, useEffect, useRef, useState, type ReactNode } from 'react'
import { api, ApiError, supabase } from './api'
import { makePost, seedPosts, type Company, type CompanyDraft, type Doc, type Post, type PostStatus } from './mock'

// Accounts and company profiles use the API; mentions, analytics and document uploads remain demos.
export type User = { name: string; email: string; role: 'analyst' | 'compliance' }

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

const mockDocsKey = (account: string) => `pg.mock-documents:${account}`

function restoreMockDocuments(companies: Company[], account: string): Company[] {
  const cached = load<Record<string, Doc[]>>(mockDocsKey(account), {}) ?? {}
  return companies.map(c => {
    const ids = new Set(c.documents.map(d => d.id))
    const docs = Array.isArray(cached[c.id]) ? cached[c.id].filter(d => !ids.has(d.id)) : []
    return { ...c, documents: [...c.documents, ...docs] }
  })
}

interface Store {
  user: User | null | undefined // undefined while the session is being restored
  authError: string | null
  sessionError: string | null
  retrySession: () => void
  signIn: () => Promise<void>
  signOut: () => void
  companies: Company[]
  addCompany: (c: CompanyDraft, docs?: Doc[]) => Promise<Company>
  updateCompany: (c: Company) => void
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
    let hydrated: string | null = null
    let pending: string | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (stopped) return
      if (!session) {
        sessionRevision.current++
        account.current = null
        hydrated = pending = null
        clearTimeout(timer)
        controller?.abort()
        setUser(null)
        setCompanies([])
        setPosts([])
        setSessionError(null)
        return
      }

      const id = session.user.id
      // Token refreshes and focus events must not reset the demo feed or a draft in progress.
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
      setSessionError(null)

      // Defer Supabase calls out of its synchronous auth callback to avoid its session lock.
      timer = setTimeout(() => {
        void Promise.all([
          api<User>('/me', { signal }),
          api<Company[]>('/companies', { signal }),
        ]).then(([profile, saved]) => {
          if (stopped || revision !== sessionRevision.current) return
          const restored = restoreMockDocuments(saved, id)
          hydrated = id
          pending = null
          setCompanies(restored)
          setPosts(restored.flatMap(seedPosts))
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
    addCompany: async (draft, docs = []) => {
      const owner = account.current
      const revision = sessionRevision.current
      if (!owner || !user) throw new Error('Please sign in before creating a company.')
      const { name, website, aliases, sector, country, people, topics } = draft
      const saved = await api<Company>('/companies', {
        method: 'POST', body: JSON.stringify({ name, website, aliases, sector, country, people, topics }),
      })
      if (account.current !== owner || revision !== sessionRevision.current) {
        throw new Error('Your session changed. Sign in again to reload your companies.')
      }
      if (docs.length) {
        const cached = load<Record<string, Doc[]>>(mockDocsKey(owner), {}) ?? {}
        save(mockDocsKey(owner), { ...cached, [saved.id]: docs })
      }
      const c = { ...saved, documents: [...saved.documents, ...docs] }
      setCompanies(cs => [...cs, c])
      setPosts(p => [...seedPosts(c), ...p].sort((a, b) => b.at - a.at))
      return c
    },
    updateCompany: c => {
      const owner = account.current
      const previous = companies.find(x => x.id === c.id)
      if (!owner || !previous) return
      const cached = load<Record<string, Doc[]>>(mockDocsKey(owner), {}) ?? {}
      const known = new Set(previous.documents.map(d => d.id))
      const demoIds = new Set((cached[c.id] ?? []).map(d => d.id))
      const docs = c.documents.filter(d => demoIds.has(d.id) || !known.has(d.id))
      save(mockDocsKey(owner), { ...cached, [c.id]: docs })
      setCompanies(cs => cs.map(x => x.id === c.id ? c : x))
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
