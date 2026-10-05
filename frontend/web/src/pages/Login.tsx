import { useState } from 'react'
import { REEL_POSTS, PLATFORM_LABEL } from '../lib/domain'
import { useStore } from '../lib/store'
import { cx, LogoMark, PlatformIcon, PRODUCT_NAME } from '../lib/ui'

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

function Logo() {
  return (
    <div className="flex flex-col items-center gap-3 text-fg-2">
      <LogoMark className="h-16" />
      <span className="font-display text-xl font-medium">{PRODUCT_NAME}</span>
    </div>
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
          {pending ? 'Signing in…' : 'Continue with Google'}
        </button>
        {authError && <p role="alert" className="mt-4 text-sm text-danger">{authError}</p>}
      </section>
    </main>
  )
}
