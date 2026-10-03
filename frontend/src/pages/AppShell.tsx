import { Bell, Buildings, ChartLine, Check, Palette, Pulse, SignOut } from '@phosphor-icons/react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { PLATFORM_LABEL } from '../lib/mock'
import { THEMES, useStore, type Theme } from '../lib/store'
import { cx, PlatformIcon, timeAgo } from '../lib/ui'
import { LogoMark, PRODUCT_NAME } from './Login'

const TABS = [
  { to: '/app/analytics', label: 'Analytics', icon: ChartLine },
  { to: '/app/feed', label: 'Live feed', icon: Pulse },
  { to: '/app/companies', label: 'Companies', icon: Buildings },
]

function Notifications({ id, placement }: { id: string; placement: string }) {
  const { posts, companies } = useStore()
  const nav = useNavigate()
  const incidents = posts.filter(p => p.severity === 'high' && p.status === 'new')
  const name = (cid: string) => companies.find(c => c.id === cid)?.name

  return (
    <>
      <button
        popoverTarget={id}
        aria-label={`Notifications, ${incidents.length} open incidents`}
        className="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-control text-sidebar-muted transition-colors duration-150 hover:bg-sidebar-active hover:text-sidebar-text"
      >
        <Bell size={20} />
        {incidents.length > 0 && (
          <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#ef4444] px-1 font-mono text-[10px] font-medium text-white">
            {incidents.length}
          </span>
        )}
      </button>
      <div id={id} popover="auto" className={cx('m-0 w-[min(360px,calc(100vw-32px))] rounded-dialog border border-line bg-surface p-0 text-fg shadow-2xl', placement)}>
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="font-semibold">Latest incidents</h2>
          <span className="text-xs text-fg-3">High priority · open</span>
        </div>
        {incidents.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-fg-3">No open high-priority incidents.</p>
        ) : (
          <ul className="max-h-96 divide-y divide-line overflow-y-auto">
            {incidents.slice(0, 6).map(p => (
              <li key={p.id}>
                <button
                  className="block w-full cursor-pointer px-4 py-3 text-left transition-colors duration-150 hover:bg-subtle"
                  onClick={() => { document.getElementById(id)?.hidePopover(); nav(`/app/feed?respond=${p.id}`) }}
                >
                  <div className="mb-1 flex items-center gap-2 text-xs text-fg-3">
                    <PlatformIcon p={p.platform} size={14} />
                    <span>{PLATFORM_LABEL[p.platform]} · {name(p.companyId)}</span>
                    <span className="ml-auto">{timeAgo(p.at)}</span>
                  </div>
                  <p className="line-clamp-2 text-sm">{p.text}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

const THEME_META: Record<Theme, { label: string; swatch: [string, string] }> = {
  graphite: { label: 'Graphite', swatch: ['#202020', '#2dd4bf'] },
  navy: { label: 'Navy', swatch: ['#111827', '#2dd4bf'] },
  laurel: { label: 'Laurel', swatch: ['#11241e', '#3cc9a6'] },
  light: { label: 'Light', swatch: ['#ffffff', '#0f766e'] },
}

function ThemeMenu({ id, placement }: { id: string; placement: string }) {
  const { theme, setTheme } = useStore()
  return (
    <>
      <button
        popoverTarget={id}
        aria-label="Change theme"
        className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-control text-sidebar-muted transition-colors duration-150 hover:bg-sidebar-active hover:text-sidebar-text"
      >
        <Palette size={20} />
      </button>
      <div id={id} popover="auto" className={cx('m-0 w-44 rounded-dialog border border-line bg-surface p-1 text-fg shadow-2xl', placement)}>
        {THEMES.map(t => (
          <button
            key={t}
            onClick={() => { setTheme(t); document.getElementById(id)?.hidePopover() }}
            aria-pressed={theme === t}
            className="flex w-full cursor-pointer items-center gap-2.5 rounded-control px-2.5 py-2 text-left text-sm transition-colors duration-150 hover:bg-subtle"
          >
            <span
              className="h-4 w-4 shrink-0 rounded-full ring-1 ring-line"
              style={{ background: `linear-gradient(135deg, ${THEME_META[t].swatch[0]} 50%, ${THEME_META[t].swatch[1]} 50%)` }}
            />
            {THEME_META[t].label}
            {theme === t && <Check size={14} className="ml-auto text-accent" />}
          </button>
        ))}
      </div>
    </>
  )
}

export default function AppShell() {
  const { user, signOut } = useStore()
  const nav = useNavigate()
  const { pathname } = useLocation()
  const title = TABS.find(t => pathname.startsWith(t.to))?.label
  const initials = user!.name.split(' ').map(w => w[0]).join('')

  const navLink = ({ isActive }: { isActive: boolean }) =>
    cx(
      'relative flex h-10 items-center gap-3 rounded-control px-3 text-sm transition-colors duration-150',
      isActive ? 'bg-sidebar-active text-sidebar-text before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-sidebar-accent' : 'text-sidebar-muted hover:bg-sidebar-active hover:text-sidebar-text',
    )

  return (
    <div className="min-h-dvh md:pl-[216px]">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-[216px] flex-col bg-sidebar p-3 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2 pt-2 text-sidebar-text">
          <LogoMark />
          <span className="font-semibold">{PRODUCT_NAME}</span>
        </div>
        <nav className="space-y-1" aria-label="Main">
          {TABS.map(t => (
            <NavLink key={t.to} to={t.to} className={navLink}>
              <t.icon size={20} />{t.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-2 border-t border-sidebar-active pt-3">
          <div className="flex items-center gap-1">
            <Notifications id="notif-desktop" placement="fixed bottom-4 left-[224px] top-auto" />
            <ThemeMenu id="theme-desktop" placement="fixed bottom-4 left-[224px] top-auto" />
            <button
              onClick={() => { signOut(); nav('/login') }}
              aria-label="Sign out"
              className="ml-auto flex h-9 w-9 cursor-pointer items-center justify-center rounded-control text-sidebar-muted transition-colors duration-150 hover:bg-sidebar-active hover:text-sidebar-text"
            >
              <SignOut size={20} />
            </button>
          </div>
          <div className="flex items-center gap-2 px-1 pb-1">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sidebar-active text-xs font-medium text-sidebar-accent">{initials}</span>
            <div className="min-w-0">
              <div className="truncate text-sm text-sidebar-text">{user!.name}</div>
              <div className="truncate text-xs text-sidebar-muted">{user!.email}</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile header */}
      <header className="sticky top-0 z-20 bg-sidebar px-4 md:hidden">
        <div className="flex h-14 items-center gap-2">
          <LogoMark />
          <span className="font-semibold text-sidebar-text">{PRODUCT_NAME}</span>
          <div className="ml-auto flex items-center gap-1">
            <Notifications id="notif-mobile" placement="fixed top-14 right-4 left-auto" />
            <ThemeMenu id="theme-mobile" placement="fixed top-14 right-4 left-auto" />
            <button onClick={() => { signOut(); nav('/login') }} aria-label="Sign out" className="flex h-11 w-11 cursor-pointer items-center justify-center text-sidebar-muted">
              <SignOut size={20} />
            </button>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto pb-2" aria-label="Main">
          {TABS.map(t => (
            <NavLink key={t.to} to={t.to} className={p => cx(navLink(p), 'h-11 shrink-0 before:hidden')}>
              <t.icon size={18} />{t.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <div className="flex h-14 items-center gap-3 border-b border-line bg-surface px-4 md:px-6">
        <h1 className="text-lg font-semibold">{title}</h1>
        <span className="ml-auto flex items-center gap-2 text-xs text-fg-3">
          <span className="h-2 w-2 rounded-full bg-[#22c55e]" aria-hidden />
          Sources active
        </span>
      </div>
      <main className="p-4 md:p-6">
        <Outlet />
      </main>
    </div>
  )
}
