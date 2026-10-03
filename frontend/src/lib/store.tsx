import { createContext, use, useEffect, useState, type ReactNode } from 'react'
import type { CompanyDraft, PendingDoc } from '../components/CompanySetup'
import { api, supabase } from './api'
import { makePost, seedPosts, type Company, type Doc, type Post, type PostStatus } from './mock'

// ponytail: auth, companies and documents are real (Supabase + API); posts are still mocks seeded per company.
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
  const [companies, setCompanies] = useState<Company[]>([])
  const [posts, setPosts] = useState<Post[]>([])
  // Older builds stored 'dark'; anything unknown falls back to graphite
  const [theme, setTheme] = useState<Theme>(() => {
    const t = load<string>('pg.theme', 'graphite')
    return (THEMES as readonly string[]).includes(t) ? (t as Theme) : 'graphite'
  })

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((_e, session) => {
      if (!session) return setUser(null)
      // Deferred: awaiting supabase calls inside this callback deadlocks the auth client.
      // Companies load before the user is set, so the router does not flash onboarding.
      setTimeout(() =>
        Promise.all([api<User>('/me'), api<Company[]>('/companies')]).then(([u, cs]) => {
          setCompanies(cs)
          setPosts(p => (p.length ? p : cs.flatMap(seedPosts))) // token refreshes must not reset the feed
          setUser(u)
        }, (e: Error) => {
          setAuthError(e.message)
          supabase.auth.signOut()
        }),
      )
    })
    return () => data.subscription.unsubscribe()
  }, [])

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
