import { createContext, use, useEffect, useState, type ReactNode } from 'react'
import { api, supabase } from './api'
import { makePost, seedPosts, type Company, type Post, type PostStatus } from './mock'

// ponytail: auth is real (Supabase + GET /me); companies/posts are still localStorage mocks until wired to the API.
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

interface Store {
  user: User | null | undefined // undefined while the session is being restored
  authError: string | null
  signIn: () => Promise<void>
  signOut: () => void
  companies: Company[]
  addCompany: (c: Company) => void
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
  const [companies, setCompanies] = useState<Company[]>(() => load('pg.companies', []))
  const [posts, setPosts] = useState<Post[]>(() => companies.flatMap(seedPosts))
  // Older builds stored 'dark'; anything unknown falls back to graphite
  const [theme, setTheme] = useState<Theme>(() => {
    const t = load<string>('pg.theme', 'graphite')
    return (THEMES as readonly string[]).includes(t) ? (t as Theme) : 'graphite'
  })

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((_e, session) => {
      if (!session) return setUser(null)
      // Deferred: awaiting supabase calls inside this callback deadlocks the auth client
      setTimeout(() =>
        api<User>('/me').then(setUser, (e: Error) => {
          setAuthError(e.message)
          supabase.auth.signOut()
        }),
      )
    })
    return () => data.subscription.unsubscribe()
  }, [])
  useEffect(() => save('pg.companies', companies), [companies])
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
    signIn: async () => {
      setAuthError(null)
      const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })
      if (error) setAuthError(error.message)
    },
    signOut: () => {
      supabase.auth.signOut()
      setUser(null)
      setCompanies([])
      setPosts([])
    },
    companies,
    addCompany: c => {
      setCompanies(cs => [...cs, c])
      setPosts(p => [...seedPosts(c), ...p].sort((a, b) => b.at - a.at))
    },
    updateCompany: c => setCompanies(cs => cs.map(x => (x.id === c.id ? c : x))),
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
