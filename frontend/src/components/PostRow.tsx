import { Archive, ArrowSquareOut, CaretDown, Lightning, Translate, UsersThree } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { sourceUrl, type Post } from '../lib/mock'
import { googleTranslateUrl, languageName, useTranslation, type TranslationState } from '../lib/translate'
import { Badge, Button, compact, cx, PlatformIcon, SeverityBadge, timeAgo, VerdictBadge } from '../lib/ui'

// "21:03 3 October 2026"
const fullDate = (t: number) => {
  const d = new Date(t)
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
  return `${time} ${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}`
}

function PostImages({ post: p }: { post: Post }) {
  const [broken, setBroken] = useState<string[]>([])
  const images = (p.images ?? []).filter(u => !broken.includes(u))
  if (images.length === 0) return null
  return (
    <div className={cx('mt-3 grid gap-2', images.length === 1 ? 'max-w-md grid-cols-1' : 'grid-cols-2 sm:grid-cols-3')}>
      {images.map(src => (
        <a key={src} href={src} target="_blank" rel="noopener noreferrer" title="Open image">
          <img src={src} alt={`Attached to the post by ${p.author || p.handle}`} loading="lazy" referrerPolicy="no-referrer"
            onError={() => setBroken(b => [...b, src])}
            className="max-h-64 w-full rounded-control border border-line object-cover" />
        </a>
      ))}
    </div>
  )
}

function TranslateButton({ tr, text }: { tr: TranslationState; text: string }) {
  const english = tr.result?.from === 'en'
  const label = tr.status === 'loading' ? 'Translating…' : tr.result ? (tr.showing ? 'Show original' : 'Show translation') : 'Translate'
  return (
    <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      {!english && (
        <button type="button" onClick={tr.run} disabled={tr.status === 'loading'}
          className="inline-flex cursor-pointer items-center gap-1 text-accent hover:underline disabled:cursor-wait disabled:opacity-60">
          <Translate size={14} />{label}
        </button>
      )}
      {tr.showing && tr.result && <span className="text-fg-3">Translated from {languageName(tr.result.from)}</span>}
      {english && <span className="text-fg-3">Already in English</span>}
      {tr.status === 'error' && (
        <span role="status" className="text-danger">
          Translation unavailable. <a href={googleTranslateUrl(text)} target="_blank" rel="noopener noreferrer" className="underline">Open in Google Translate</a>
        </span>
      )}
    </span>
  )
}

export function PostRow({ post: p, companyName, actionable, onDismiss, onRespond }: {
  post: Post
  companyName?: string
  actionable: boolean
  onDismiss: () => void
  onRespond: () => void
}) {
  const [open, setOpen] = useState(false)
  const tr = useTranslation(p.text)
  const shown = tr.showing && tr.result ? tr.result.text : p.text
  // Expandable only when there is more to show: text cut off by the 3-line clamp, or pictures
  const textRef = useRef<HTMLParagraphElement>(null)
  const [clamped, setClamped] = useState(false)
  useEffect(() => {
    const el = textRef.current
    if (!el || open) return // while open the clamp is off, so keep the last measurement
    const measure = () => setClamped(el.scrollHeight > el.clientHeight + 1)
    const ro = new ResizeObserver(measure) // also fires once on observe
    ro.observe(el)
    return () => ro.disconnect()
  }, [open, shown])
  const expandable = clamped || (p.images?.length ?? 0) > 0
  const bodyId = `post-body-${p.id}`
  // News items are stored as "headline — excerpt"
  const [headline, ...rest] = open && p.platform === 'news' ? shown.split(' — ') : ['', shown]
  const text = rest.join(' — ')
  const toggle = () => setOpen(o => !o)

  return (
    <li className={cx('motion-control', p.status !== 'new' && 'opacity-70')}>
      <div className="flex gap-3 p-4">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-subtle text-fg-2"><PlatformIcon p={p.platform} size={16} /></span>
        <div id={bodyId} className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="truncate font-semibold">{p.author || p.handle}</span>
            {p.author && p.handle && <span className="truncate text-xs text-fg-3">{p.handle}</span>}
            <span aria-hidden className="text-xs text-fg-3">·</span>
            <time className="shrink-0 cursor-default text-xs text-fg-3" dateTime={new Date(p.at).toISOString()} title={fullDate(p.at)}>
              {timeAgo(p.at)}
            </time>
          </div>
          {headline && <h3 className="mt-1 text-[15px] leading-6 font-semibold">{headline}</h3>}
          <p ref={textRef} className={cx('mt-1 text-[15px] leading-6 break-words whitespace-pre-line', !open && 'line-clamp-3')}>{text}</p>
          {open && p.platform === 'news' && <p className="mt-1 text-xs text-fg-3">News sources provide only the headline and a short excerpt. Open the source for the full article.</p>}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <TranslateButton tr={tr} text={p.text} />
            {expandable && (
              <button type="button" onClick={toggle} aria-expanded={open} aria-controls={bodyId}
                className="cursor-pointer text-xs text-fg-2 hover:text-fg">{open ? 'Show less' : 'Show more'}</button>
            )}
          </div>
          {open && <PostImages post={p} />}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="flex flex-wrap gap-1.5">
              {companyName && <Badge>{companyName}</Badge>}
              <SeverityBadge s={p.severity} />
              <VerdictBadge v={p.verdict} />
              {p.status === 'responded' && <Badge tone="success">Responded</Badge>}
              {p.status === 'dismissed' && <Badge><Archive size={14} />Dismissed</Badge>}
            </div>
            <div className="flex items-center gap-3 text-xs text-fg-3">
              <span className="flex items-center gap-1"><Lightning size={14} /><span className="font-mono text-fg-2">{compact(p.reach)}</span> reach</span>
              {p.cluster && <span className="flex items-center gap-1"><UsersThree size={14} /><span className="font-mono text-fg-2">{p.cluster.size}</span> similar</span>}
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1 self-center">
          {actionable && <Button variant="ghost" className="w-9 px-0" aria-label="Dismiss" title="Dismiss" onClick={onDismiss}><Archive size={16} /></Button>}
          {expandable && (
            <Button variant="ghost" className="w-9 px-0" aria-label={open ? 'Collapse post' : 'Expand post'} title={open ? 'Collapse' : 'Expand'}
              aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
              <CaretDown size={16} className={cx('motion-control', open && 'rotate-180')} />
            </Button>
          )}
          <a
            href={sourceUrl(p)}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open source"
            title="Open source"
            className="inline-flex size-9 items-center justify-center rounded-control text-fg-2 motion-control hover:bg-subtle hover:text-fg"
          ><ArrowSquareOut size={16} /></a>
          {actionable && <Button className="ml-1" onClick={onRespond}>Counter-post</Button>}
        </div>
      </div>
    </li>
  )
}
