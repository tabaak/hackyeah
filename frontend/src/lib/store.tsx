import { createContext, use, useEffect, useState, type ReactNode } from 'react'
import { DEMO_USER, makePost, seedPosts, type Company, type Post, type PostStatus } from './mock'

// ponytail: localStorage-backed mock session; swap for Supabase Auth + TanStack Query when the API lands.
type User = typeof DEMO_USER

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
  user: User | null
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
  const [user, setUser] = useState<User | null>(() => load('pg.user', null))
  const [companies, setCompanies] = useState<Company[]>(() => load('pg.companies', []))
  const [posts, setPosts] = useState<Post[]>(() => companies.flatMap(seedPosts))
  // Older builds stored 'dark'; anything unknown falls back to graphite
  const [theme, setTheme] = useState<Theme>(() => {
    const t = load<string>('pg.theme', 'graphite')
    return (THEMES as readonly string[]).includes(t) ? (t as Theme) : 'graphite'
  })

  useEffect(() => save('pg.user', user), [user])
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
    signIn: async () => {
      await new Promise(r => setTimeout(r, 700))
      setUser(DEMO_USER)
    },
    signOut: () => {
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
