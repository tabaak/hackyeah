import { ChatsCircle, CheckCircle, GitDiff, Question, Warning, X as XIcon } from '@phosphor-icons/react'
import facebookIcon from '../assets/platforms/facebook.svg'
import newsIcon from '../assets/platforms/news.svg'
import threadsIcon from '../assets/platforms/threads.svg'
import xIcon from '../assets/platforms/x.svg'
import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { PLATFORM_LABEL, VERDICT_LABEL, type Classification, type Platform, type Severity, type Verdict } from './mock'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
const VARIANT: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent hover:bg-accent-hover',
  secondary: 'border border-control text-fg hover:bg-subtle',
  ghost: 'text-fg-2 hover:bg-subtle hover:text-fg',
  danger: 'bg-danger-bg text-danger border border-danger/40 hover:border-danger',
}
export function Button({ variant = 'secondary', className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...p}
      className={cx(
        'inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-control px-3 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT[variant], className,
      )}
    />
  )
}

export const inputCls =
  'h-9 rounded-control border border-control bg-surface px-3 text-sm text-fg placeholder:text-fg-3 focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/20'

export function Field({ label, hint, children, optional }: { label: string; hint?: string; children: ReactNode; optional?: boolean }) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-fg">
        {label} {optional && <span className="font-normal text-fg-3">· optional</span>}
      </span>
      {children}
      {hint && <span className="block text-xs text-fg-3">{hint}</span>}
    </label>
  )
}

export function Badge({ tone = 'neutral', children, className }: { tone?: 'neutral' | 'danger' | 'warning' | 'info' | 'success' | 'ready'; children: ReactNode; className?: string }) {
  const t = {
    neutral: 'bg-subtle text-neutral',
    danger: 'bg-danger-bg text-danger',
    warning: 'bg-warning-bg text-warning',
    info: 'bg-info-bg text-info',
    success: 'bg-success-bg text-success',
    ready: 'bg-ready-bg text-ready',
  }[tone]
  return <span className={cx('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium', t, className)}>{children}</span>
}

export function SeverityBadge({ s }: { s: Severity }) {
  if (s === 'high') return <Badge tone="danger"><Warning size={14} weight="bold" />High</Badge>
  if (s === 'medium') return <Badge tone="warning">Medium</Badge>
  return <Badge>Low</Badge>
}

export function VerdictBadge({ v }: { v: Verdict }) {
  const icon = { contradicted_by_documents: <GitDiff size={14} />, supported_by_documents: <CheckCircle size={14} />, insufficient_evidence: <Question size={14} />, opinion: <ChatsCircle size={14} /> }[v]
  const tone = v === 'contradicted_by_documents' ? 'info' : v === 'insufficient_evidence' ? 'warning' : 'neutral'
  return <Badge tone={tone}>{icon}{VERDICT_LABEL[v]}</Badge>
}

export function ClassBadge({ c }: { c: Classification }) {
  const tone = c === 'restricted' ? 'danger' : c === 'confidential' ? 'warning' : c === 'internal' ? 'info' : 'neutral'
  return <Badge tone={tone} className="font-mono uppercase tracking-wide">{c}</Badge>
}

// Simple Icons brand marks (news: Phosphor fill); painted via mask so they take currentColor
const PLATFORM_ICON: Record<Platform, string> = { x: xIcon, facebook: facebookIcon, threads: threadsIcon, news: newsIcon }
export function PlatformIcon({ p, size = 16 }: { p: Platform; size?: number }) {
  const mask = `url("${PLATFORM_ICON[p]}") center / contain no-repeat`
  return <span role="img" aria-label={PLATFORM_LABEL[p]} className="inline-block shrink-0 bg-current" style={{ width: size, height: size, mask, WebkitMask: mask }} />
}

export function timeAgo(t: number) {
  const m = Math.round((Date.now() - t) / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`
}

export const compact = (n: number) => Intl.NumberFormat('en', { notation: 'compact' }).format(n)

// Native <dialog>: Escape, focus trap and focus return come from the browser.
export function Dialog({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={e => e.target === ref.current && onClose()}
      className={cx('m-auto max-h-[90vh] w-[calc(100%-32px)] rounded-dialog border border-line bg-surface p-0 text-fg shadow-2xl', wide ? 'max-w-3xl' : 'max-w-lg')}
    >
      {open && (
        <div className="flex max-h-[90vh] flex-col">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-lg font-semibold">{title}</h2>
            <Button variant="ghost" className="w-9 px-0" onClick={onClose} aria-label="Close"><XIcon size={18} /></Button>
          </div>
          <div className="overflow-y-auto p-5">{children}</div>
        </div>
      )}
    </dialog>
  )
}
