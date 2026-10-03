import { GoogleLogo, ShieldCheck, Spinner, Warning } from '@phosphor-icons/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { REEL_POSTS, PLATFORM_LABEL } from '../lib/mock'
import { useStore } from '../lib/store'
import { cx, PlatformIcon } from '../lib/ui'

export const PRODUCT_NAME = 'ProofGate'

function PostCard({ p }: { p: (typeof REEL_POSTS)[number] }) {
  return (
    <div
      className={cx(
        'relative mb-3 rounded-panel border bg-surface p-3 text-[13px] leading-5 shadow-sm',
        p.threat ? 'border-danger/60' : 'border-line',
      )}
    >
      <div className="mb-1.5 flex items-center gap-2 text-xs text-fg-3">
        <PlatformIcon p={p.platform} size={14} />
        <span className="truncate">{PLATFORM_LABEL[p.platform]} · {p.handle}</span>
      </div>
      <p className="text-fg-2">{p.text}</p>
      {p.threat && (
        <span className="threat-scan absolute -top-2 right-2 inline-flex items-center gap-1 rounded-full bg-danger-bg px-2 py-0.5 text-[11px] font-medium text-danger ring-1 ring-danger/50">
          <Warning size={12} weight="bold" /> Threat detected
        </span>
      )}
    </div>
  )
}

// A column of posts duplicated once so translateY(-50%) loops seamlessly.
function Reel({ offset, dir, speed, tilt }: { offset: number; dir: 'up' | 'down'; speed: number; tilt: number }) {
  const posts = [...REEL_POSTS.slice(offset), ...REEL_POSTS.slice(0, offset)]
  return (
    <div className="h-full w-60 shrink-0 overflow-hidden" style={{ transform: `rotateY(${tilt}deg)` }}>
      <div className={dir === 'up' ? 'reel-up' : 'reel-down'} style={{ ['--reel-speed' as string]: `${speed}s` }}>
        {[...posts, ...posts].map((p, i) => <PostCard key={i} p={p} />)}
      </div>
    </div>
  )
}

const FADE = { maskImage: 'linear-gradient(to bottom, transparent, black 18%, black 82%, transparent)' }

export default function Login() {
  const { signIn } = useStore()
  const nav = useNavigate()
  const [pending, setPending] = useState(false)

  async function go() {
    setPending(true)
    await signIn()
    nav('/', { replace: true })
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-canvas px-4">
      {/* Left and right drums of posts, tilted toward the centre */}
      <div aria-hidden className="pointer-events-none absolute inset-y-0 left-0 hidden gap-3 pl-6 lg:flex" style={{ perspective: '900px', ...FADE }}>
        <Reel offset={0} dir="up" speed={70} tilt={28} />
        <Reel offset={5} dir="down" speed={55} tilt={18} />
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 hidden gap-3 pr-6 lg:flex" style={{ perspective: '900px', ...FADE }}>
        <Reel offset={3} dir="down" speed={60} tilt={-18} />
        <Reel offset={8} dir="up" speed={75} tilt={-28} />
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,var(--canvas)_30%,transparent_70%)]" />

      <section className="relative z-10 w-full max-w-sm rounded-dialog border border-line bg-surface/95 p-8 text-center shadow-2xl backdrop-blur">
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-selected text-accent">
          <ShieldCheck size={28} weight="duotone" />
        </div>
        <h1 className="text-2xl font-semibold">{PRODUCT_NAME}</h1>
        <p className="mt-2 text-[15px] leading-6 text-fg-2">
          Thousands of posts mention your company every day. We find the few that are attacks — and help you answer with evidence, in minutes.
        </p>
        <ul className="mt-5 space-y-1.5 text-left text-sm text-fg-2">
          <li className="flex gap-2"><span className="text-accent">●</span>Monitor X, Telegram, Reddit, TikTok and news</li>
          <li className="flex gap-2"><span className="text-danger">●</span>Spot coordinated disinformation early</li>
          <li className="flex gap-2"><span className="text-info">●</span>Draft counter-posts verified by your documents</li>
        </ul>
        <button
          onClick={go}
          disabled={pending}
          className="mt-7 inline-flex h-11 w-full cursor-pointer items-center justify-center gap-3 rounded-control bg-fg text-sm font-medium text-canvas transition-opacity duration-150 hover:opacity-90 disabled:opacity-60"
        >
          {pending ? <Spinner size={18} className="animate-spin" /> : <GoogleLogo size={18} weight="bold" />}
          {pending ? 'Signing in…' : 'Continue with Google'}
        </button>
        <p className="mt-4 text-xs text-fg-3">Demo · fictional organizations, synthetic data</p>
      </section>
    </main>
  )
}
