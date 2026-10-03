import { Spinner } from '@phosphor-icons/react'
import { useState } from 'react'
import logoFigure from '../assets/logo-figure.png'
import { REEL_POSTS, PLATFORM_LABEL } from '../lib/mock'
import { useStore } from '../lib/store'
import { cx, PlatformIcon } from '../lib/ui'

export const PRODUCT_NAME = 'Palladion'

function PostCard({ p }: { p: (typeof REEL_POSTS)[number] }) {
  return (
    <div
      className={cx(
        'mb-3 rounded-panel border bg-surface p-3 text-[13px] leading-5 shadow-sm',
        p.threat ? 'border-danger/25' : 'border-line',
      )}
    >
      <div className="mb-1.5 flex items-center gap-2 text-xs text-fg-3">
        <PlatformIcon p={p.platform} size={14} />
        <span className="truncate">{PLATFORM_LABEL[p.platform]} · {p.handle}</span>
        {p.threat && (
          <span className="threat-scan ml-auto flex shrink-0 items-center gap-1 text-[11px] text-danger">
            Threat
          </span>
        )}
      </div>
      <p className="text-fg-2">{p.text}</p>
    </div>
  )
}

export function LogoMark({ className = 'h-8' }: { className?: string }) {
  return <img src={logoFigure} alt="" className={cx('w-auto', className)} />
}

function Logo() {
  return (
    <div className="flex flex-col items-center gap-3 text-fg-2">
      <LogoMark className="h-16" />
      <span className="font-display text-xl font-medium">{PRODUCT_NAME}</span>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z" />
    </svg>
  )
}

// A column of posts duplicated once so translateY(-50%) loops seamlessly.
function Reel({ offset, dir, speed, tilt, className }: { offset: number; dir: 'up' | 'down'; speed: number; tilt: number; className?: string }) {
  const posts = [...REEL_POSTS.slice(offset), ...REEL_POSTS.slice(0, offset)]
  return (
    <div className={cx('h-full w-60 shrink-0 overflow-hidden', className)} style={{ transform: `rotateY(${tilt}deg)` }}>
      <div className={dir === 'up' ? 'reel-up' : 'reel-down'} style={{ ['--reel-speed' as string]: `${speed}s` }}>
        {[...posts, ...posts].map((p, i) => <PostCard key={i} p={p} />)}
      </div>
    </div>
  )
}

const FADE = { maskImage: 'linear-gradient(to bottom, transparent, black 18%, black 82%, transparent)' }

export default function Login() {
  const { signIn, authError } = useStore()
  const [pending, setPending] = useState(false)

  // Redirects to Google; on return the store picks up the session and Gate routes onward
  async function go() {
    setPending(true)
    await signIn()
    setPending(false)
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-canvas px-4">
      {/* Left and right drums of posts, tilted toward the centre; below lg only the outer reel peeks in, dimmed */}
      <div aria-hidden className="pointer-events-none absolute inset-y-0 -left-48 flex gap-3 pl-6 opacity-30 md:-left-32 md:opacity-50 lg:left-0 lg:opacity-100" style={{ perspective: '900px', ...FADE }}>
        <Reel offset={0} dir="up" speed={70} tilt={28} />
        <Reel offset={5} dir="down" speed={55} tilt={18} className="hidden lg:block" />
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-y-0 -right-48 flex gap-3 pr-6 opacity-30 md:-right-32 md:opacity-50 lg:right-0 lg:opacity-100" style={{ perspective: '900px', ...FADE }}>
        <Reel offset={3} dir="down" speed={60} tilt={-18} className="hidden lg:block" />
        <Reel offset={8} dir="up" speed={75} tilt={-28} />
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,var(--canvas)_40%,transparent_75%)]" />

      <section className="motion-page relative z-10 w-full max-w-xl text-center">
        <Logo />
        <h1 className="mt-8 text-balance font-display text-6xl font-medium leading-[1.02] tracking-[-0.02em] sm:text-7xl">Catch the attack before it trends</h1>
        <p className="mx-auto mt-6 max-w-md text-balance text-lg leading-7 text-fg-2">
          We track X, Telegram, Reddit, TikTok and news, flag disinformation about your company and draft replies backed by your documents
        </p>
        <button
          onClick={go}
          disabled={pending}
          className="motion-control motion-press mt-10 inline-flex h-13 w-full max-w-xs cursor-pointer items-center justify-center gap-3 rounded-control border border-line bg-white text-base font-medium text-[#1f1f1f] shadow-sm hover:bg-[#f2f2f2] disabled:opacity-60"
        >
          {pending ? <Spinner size={20} className="animate-spin" /> : <GoogleIcon />}
          {pending ? 'Signing in…' : 'Continue with Google'}
        </button>
        {authError && <p role="alert" className="mt-4 text-sm text-danger">{authError}</p>}
      </section>
    </main>
  )
}
