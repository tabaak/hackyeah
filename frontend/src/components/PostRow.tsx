import { Archive, ArrowSquareOut, CaretDown, Lightning, Translate, UsersThree } from '@phosphor-icons/react'
import { useState } from 'react'
import { PLATFORM_LABEL, sourceUrl, type Post } from '../lib/mock'
import { googleTranslateUrl, languageName, useTranslation, type TranslationState } from '../lib/translate'
import { Badge, Button, compact, cx, PlatformIcon, SeverityBadge, timeAgo, VerdictBadge } from '../lib/ui'

const LONG_TEXT = 200 // characters after which three lines are probably not enough

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase()).join('') || '?'

// Picture of the author, in the source's own words: a link we do not control, so it can break or expire.
function Avatar({ post, size = 40 }: { post: Post; size?: number }) {
  const [failed, setFailed] = useState(false)
  const src = post.avatarUrl || (post.platform === 'news' && post.handle ? `https://www.google.com/s2/favicons?domain=${post.handle}&sz=64` : null)
  const box = { width: size, height: size }
  if (!src || failed) {
    return <span aria-hidden style={box} className="grid shrink-0 place-items-center rounded-full bg-surface text-sm font-medium text-fg-2">{initials(post.author || post.handle)}</span>
  }
  return <img src={src} alt="" style={box} referrerPolicy="no-referrer" onError={() => setFailed(true)} className="shrink-0 rounded-full bg-surface object-cover" />
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

function PostDetails({ id, post: p, shown, tr }: { id: string; post: Post; shown: string; tr: TranslationState }) {
  const [broken, setBroken] = useState<string[]>([])
  const images = (p.images ?? []).filter(u => !broken.includes(u))
  // News items are stored as "headline — excerpt"
  const [headline, ...rest] = p.platform === 'news' ? shown.split(' — ') : ['', shown]
  const body = rest.join(' — ')
  const date = new Date(p.at)

  return (
    <div id={id} className="border-t border-line bg-subtle px-4 py-4">
      <div className="flex items-start gap-3">
        <Avatar post={p} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-semibold">{p.author || p.handle}</span>
            {p.author && p.handle && <span className="truncate text-sm text-fg-3">{p.handle}</span>}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-fg-3">
            <PlatformIcon p={p.platform} size={12} />
            <span>{PLATFORM_LABEL[p.platform]}</span>
            <span aria-hidden>·</span>
            <time dateTime={date.toISOString()}>{date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time>
            <span>({timeAgo(p.at)})</span>
          </div>
        </div>
        <a href={sourceUrl(p)} target="_blank" rel="noopener noreferrer"
          className="inline-flex shrink-0 items-center gap-1 text-sm text-fg-2 motion-control hover:text-fg">
          Open source<ArrowSquareOut size={14} />
        </a>
      </div>

      <div className="mt-4 space-y-2">
        {headline && <h3 className="text-[15px] leading-6 font-semibold">{headline}</h3>}
        {body && <p className="text-[15px] leading-6 break-words whitespace-pre-wrap">{body}</p>}
        {p.platform === 'news' && <p className="text-xs text-fg-3">News sources provide only the headline and a short excerpt. Open the source for the full article.</p>}
        <TranslateButton tr={tr} text={p.text} />
      </div>

      {images.length > 0 && (
        <div className={cx('mt-4 grid gap-2', images.length === 1 ? 'max-w-md grid-cols-1' : 'grid-cols-2 sm:grid-cols-3')}>
          {images.map(src => (
            <a key={src} href={src} target="_blank" rel="noopener noreferrer" title="Open image">
              <img src={src} alt={`Attached to the post by ${p.author || p.handle}`} loading="lazy" referrerPolicy="no-referrer"
                onError={() => setBroken(b => [...b, src])}
                className="max-h-64 w-full rounded-control border border-line object-cover" />
            </a>
          ))}
        </div>
      )}
    </div>
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
  const long = shown.length > LONG_TEXT || shown.includes('\n')
  const panelId = `post-details-${p.id}`

  return (
    <li className={cx('motion-control', p.status !== 'new' && 'opacity-70')}>
      <div className="flex gap-3 p-4">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-subtle text-fg-2"><PlatformIcon p={p.platform} size={16} /></span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="truncate font-semibold">{companyName}</span>
            <span className="truncate text-xs text-fg-3">{p.handle}</span>
            <span aria-hidden className="text-xs text-fg-3">·</span>
            <time className="shrink-0 text-xs text-fg-3" dateTime={new Date(p.at).toISOString()} title={new Date(p.at).toLocaleString()}>{timeAgo(p.at)}</time>
          </div>
          <p className="mt-1 line-clamp-3 text-[15px] leading-6 break-words whitespace-pre-line">{shown}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <TranslateButton tr={tr} text={p.text} />
            {long && !open && (
              <button type="button" onClick={() => setOpen(true)} className="cursor-pointer text-xs text-fg-2 hover:text-fg">Show more</button>
            )}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="flex flex-wrap gap-1.5">
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
          <Button variant="ghost" className="w-9 px-0" aria-label={open ? 'Hide details' : 'Show details'} title={open ? 'Hide details' : 'Show details'}
            aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(o => !o)}>
            <CaretDown size={16} className={cx('motion-control', open && 'rotate-180')} />
          </Button>
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
      {open && <PostDetails id={panelId} post={p} shown={shown} tr={tr} />}
    </li>
  )
}
