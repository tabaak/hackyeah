import { lazy, StrictMode, Suspense, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import { StoreProvider, useStore } from './lib/store'
import AppShell from './pages/AppShell'
import Companies from './pages/Companies'
import LiveFeed from './pages/LiveFeed'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'

const Analytics = lazy(() => import('./pages/Analytics')) // recharts stays out of the initial bundle

// login → onboarding (first company) → app
function Gate({ need, children }: { need: 'guest' | 'onboarding' | 'app'; children: ReactNode }) {
  const { user, companies } = useStore()
  if (user === undefined) return null // restoring session
  const at = !user ? 'guest' : companies.length === 0 ? 'onboarding' : 'app'
  if (at === need) return children
  return <Navigate to={{ guest: '/login', onboarding: '/onboarding', app: '/app/feed' }[at]} replace />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <StoreProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Gate need="guest"><Login /></Gate>} />
          <Route path="/onboarding" element={<Gate need="onboarding"><Onboarding /></Gate>} />
          <Route path="/app" element={<Gate need="app"><AppShell /></Gate>}>
            <Route path="analytics" element={<Suspense><Analytics /></Suspense>} />
            <Route path="feed" element={<LiveFeed />} />
            <Route path="companies" element={<Companies />} />
            <Route index element={<Navigate to="feed" replace />} />
          </Route>
          <Route path="*" element={<Gate need="app"><Navigate to="/app/feed" replace /></Gate>} />
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  </StrictMode>,
)
