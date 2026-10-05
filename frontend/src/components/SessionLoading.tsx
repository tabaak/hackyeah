import type { CSSProperties } from 'react'
import { useStore } from '../lib/store'
import { Button, cx, LogoMark, PRODUCT_NAME } from '../lib/ui'

const delay = (ms: number) => ({ ['--loader-delay' as string]: `${ms}ms` })

function Bone({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div className={cx('skeleton rounded-control', className)} style={style} />
}

// Fixed widths so the placeholder text lines look ragged but never jump between renders
const NAV_WIDTHS = ['62%', '54%', '70%']
const ROW_WIDTHS = ['88%', '64%', '76%', '52%', '82%', '68%']

function SessionError({ message }: { message: string }) {
  const { retrySession, signOut } = useStore()
  return (
    <main className="flex min-h-dvh items-center justify-center bg-canvas px-4">
      <section className="flex w-full max-w-xs flex-col items-center text-center">
        <div className="loader-in" style={delay(0)}><LogoMark className="h-14" /></div>
        <span className="loader-in mt-5 font-display text-2xl font-medium tracking-[-0.01em] text-fg" style={delay(80)}>
          {PRODUCT_NAME}
        </span>
        <div className="loader-in flex flex-col items-center" style={delay(160)}>
          <p role="alert" className="mt-6 text-balance text-sm text-fg-2">{message}</p>
          <div className="mt-5 flex gap-2">
            <Button variant="primary" onClick={retrySession}>Try again</Button>
            <Button variant="ghost" onClick={signOut}>Sign out</Button>
          </div>
        </div>
      </section>
    </main>
  )
}

// Mirrors the AppShell layout so the real app replaces it without the page jumping
export default function SessionLoading() {
  const { sessionError } = useStore()
  if (sessionError) return <SessionError message={sessionError} />

  return (
    <div role="status" aria-label="Loading your workspace" className="skeleton-in min-h-dvh md:pl-[216px]">
      {/* Desktop sidebar */}
      <aside aria-hidden className="skeleton-on-sidebar fixed inset-y-0 left-0 hidden w-[216px] flex-col bg-sidebar p-3 md:flex">
        <div className="mb-3 flex items-center gap-3 border-b border-sidebar-active px-2 pt-2 pb-3 text-sidebar-text">
          <LogoMark />
          <span className="translate-y-[3px] font-display text-[28px] font-medium leading-none tracking-tight">{PRODUCT_NAME}</span>
        </div>
        <div className="space-y-1">
          {NAV_WIDTHS.map(w => (
            <div key={w} className="flex h-10 items-center gap-3 px-3">
              <Bone className="size-5" />
              <Bone className="h-3" style={{ width: w }} />
            </div>
          ))}
        </div>
        <div className="mt-auto space-y-2 border-t border-sidebar-active pt-3">
          <div className="flex items-center gap-1">
            <Bone className="m-1.5 size-6" />
            <Bone className="m-1.5 size-6" />
            <Bone className="m-1.5 ml-auto size-6" />
          </div>
          <div className="flex items-center gap-2 px-1 pb-1">
            <Bone className="size-8 shrink-0 rounded-full" />
            <div className="flex-1 space-y-1.5">
              <Bone className="h-3 w-3/4" />
              <Bone className="h-2.5 w-full" />
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile header */}
      <header aria-hidden className="skeleton-on-sidebar sticky top-0 z-20 bg-sidebar px-4 md:hidden">
        <div className="flex h-14 items-center gap-2.5">
          <LogoMark />
          <span className="translate-y-[3px] font-display text-2xl font-medium leading-none tracking-tight text-sidebar-text">{PRODUCT_NAME}</span>
          <div className="ml-auto flex items-center gap-4 pr-2.5">
            <Bone className="size-6" />
            <Bone className="size-6" />
            <Bone className="size-6" />
          </div>
        </div>
      </header>

      {/* Mobile tab bar */}
      <div aria-hidden className="skeleton-on-sidebar fixed inset-x-0 bottom-0 z-20 flex border-t border-sidebar-active bg-sidebar pb-[env(safe-area-inset-bottom)] md:hidden">
        {NAV_WIDTHS.map(w => (
          <div key={w} className="flex h-14 flex-1 flex-col items-center justify-center gap-1.5">
            <Bone className="size-5" />
            <Bone className="h-2 w-12" />
          </div>
        ))}
      </div>

      <main aria-hidden className="p-4 pb-[calc(5rem+env(safe-area-inset-bottom))] md:p-6">
        <Bone className="mb-6 h-6 w-32 md:h-7 md:w-40" />
        <section className="rounded-panel border border-line bg-surface max-sm:-mx-4 max-sm:rounded-none max-sm:border-x-0">
          <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
            <Bone className="mr-auto h-5 w-36" />
            <Bone className="h-9 w-full sm:w-56" />
            <Bone className="hidden h-9 w-32 sm:block" />
            <Bone className="hidden h-9 w-32 lg:block" />
          </div>
          <ul className="divide-y divide-line">
            {ROW_WIDTHS.map(w => (
              <li key={w} className="flex gap-3 p-4">
                <Bone className="size-8 shrink-0 rounded-full" />
                <div className="min-w-0 flex-1 space-y-2.5">
                  <div className="flex items-center gap-2">
                    <Bone className="h-3.5 w-28" />
                    <Bone className="h-3 w-20" />
                    <Bone className="ml-auto h-3 w-10" />
                  </div>
                  <Bone className="h-3.5 w-full" />
                  <Bone className="h-3.5" style={{ width: w }} />
                  <div className="flex gap-2 pt-1">
                    <Bone className="h-5 w-16 rounded-full" />
                    <Bone className="h-5 w-20 rounded-full" />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}
