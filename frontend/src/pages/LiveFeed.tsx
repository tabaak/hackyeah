import { Archive, ArrowCounterClockwise, ArrowSquareOut, Lightning, Quotes, UsersThree, Warning } from '@phosphor-icons/react'
import { useSearchParams } from 'react-router-dom'
import { CounterPost } from '../components/CounterPost'
import { PLATFORM_LABEL, sourceUrl, type Platform, type Post } from '../lib/mock'
import { useStore } from '../lib/store'
import { Badge, Button, compact, cx, Dialog, PlatformIcon, SeverityBadge, timeAgo, VerdictBadge } from '../lib/ui'

// Matches the severity segmented control
const filterCls = 'h-[38px] cursor-pointer rounded-control border border-line bg-surface px-3 text-sm text-fg-2 transition-colors duration-150 hover:text-fg focus:outline-none focus-visible:border-accent'

const SEVERITIES = ['all', 'high', 'medium', 'low'] as const
const STATUSES = { open: 'Open', responded: 'Responded', dismissed: 'Dismissed', all: 'All' } as const

const actionable = (p: Post) => p.status === 'new' && p.severity !== 'low'

export default function LiveFeed() {
  const { posts, companies, setPostStatus } = useStore()
  const [q, setQ] = useSearchParams()
  const company = q.get('company') ?? 'all'
  const severity = q.get('severity') ?? 'all'
  const platform = q.get('platform') ?? 'all'
  const status = (q.get('status') ?? 'open') as keyof typeof STATUSES
  const respondId = q.get('respond')

  const set = (k: string, v: string | null) =>
    setQ(prev => {
      const n = new URLSearchParams(prev)
      if (v == null || v === 'all' || (k === 'status' && v === 'open')) n.delete(k)
      else n.set(k, v)
      return n
    }, { replace: k === 'respond' })

  const nameOf = (id: string) => companies.find(c => c.id === id)?.name
  const responding = posts.find(p => p.id === respondId)
  const respondingCompany = companies.find(c => c.id === responding?.companyId)

  const urgent = posts
    .filter(p => p.severity === 'high' && p.status === 'new' && (company === 'all' || p.companyId === company))
    .sort((a, b) => b.reach - a.reach)
    .slice(0, 3)

  const list = posts.filter(p =>
    (company === 'all' || p.companyId === company) &&
    (severity === 'all' || p.severity === severity) &&
    (platform === 'all' || p.platform === platform) &&
    (status === 'all' || (status === 'open' ? p.status === 'new' : p.status === status)),
  )
  const filtered = q.has('company') || q.has('severity') || q.has('platform') || q.has('status')

  return (
    <div className="space-y-6">
      {urgent.length > 0 && (
        <section aria-labelledby="urgent-h">
          <div className="mb-3 flex items-center gap-2">
            <Warning size={20} weight="fill" className="text-danger" />
            <h2 id="urgent-h" className="text-lg font-semibold">Needs attention</h2>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {urgent.map(p => (
              <article key={p.id} className="flex flex-col overflow-hidden rounded-panel border border-danger/40 bg-surface">
                <header className="flex items-start gap-3 px-4 pt-4">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-subtle text-fg-2"><PlatformIcon p={p.platform} size={18} /></span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{nameOf(p.companyId)}</p>
                    <p className="truncate text-xs text-fg-3">{p.handle}</p>
                  </div>
                  <time className="shrink-0 text-xs text-fg-3" dateTime={new Date(p.at).toISOString()} title={new Date(p.at).toLocaleString()}>{timeAgo(p.at)}</time>
                </header>

                {p.injection && (
                  <div className="px-4 pt-3">
                    <Badge tone="danger"><Warning size={14} weight="bold" />AI manipulation</Badge>
                  </div>
                )}

                <figure className="mx-4 mt-3">
                  <Quotes size={20} weight="fill" className="text-fg-3/60" aria-hidden />
                  <blockquote className="mt-1 line-clamp-3 text-[15px] leading-6">{p.text}</blockquote>
                </figure>

                <div className="mx-4 mb-4 mt-4 rounded-control bg-subtle px-3 py-2.5">
                  <p className="text-[11px] font-medium uppercase tracking-wider text-fg-3">Why flagged</p>
                  <p className="mt-1 line-clamp-3 text-sm text-fg-2">{p.reason}</p>
                </div>

                <dl className="mt-auto grid grid-cols-2 divide-x divide-line border-y border-line">
                  <div className="px-4 py-3">
                    <dt className="flex items-center gap-1 text-xs text-fg-3"><Lightning size={14} />Reach</dt>
                    <dd className="mt-0.5 font-mono text-lg font-semibold">{compact(p.reach)}</dd>
                  </div>
                  <div className="px-4 py-3">
                    <dt className="flex items-center gap-1 text-xs text-fg-3"><UsersThree size={14} />Cluster</dt>
                    <dd className="mt-0.5 font-mono text-lg font-semibold">
                      {p.cluster ? <>{p.cluster.size} <span className="font-sans text-xs font-normal text-fg-3">posts · {p.cluster.accounts} accts</span></> : <span className="text-fg-3">—</span>}
                    </dd>
                  </div>
                </dl>

                <div className="flex gap-2 p-4">
                  <Button variant="primary" className="flex-1" onClick={() => set('respond', p.id)}>
                    Create counter-post
                  </Button>
                  <Button variant="ghost" aria-label="Dismiss" title="Dismiss" onClick={() => setPostStatus(p.id, 'dismissed')}><Archive size={16} /></Button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section aria-labelledby="feed-h" className="rounded-panel border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-3 rounded-t-panel border-b border-line bg-surface p-4 lg:sticky lg:top-0 lg:z-10">
          <h2 id="feed-h" className="mr-auto text-lg font-semibold">All mentions <span className="font-mono text-sm font-normal text-fg-3">{list.length}</span></h2>
          <div role="group" aria-label="Severity" className="flex rounded-control border border-line p-0.5">
            {SEVERITIES.map(s => (
              <button
                key={s}
                aria-pressed={severity === s}
                onClick={() => set('severity', s)}
                className={cx('h-8 cursor-pointer rounded-[4px] px-3 text-sm capitalize transition-colors duration-150', severity === s ? 'bg-selected font-medium text-fg' : 'text-fg-2 hover:text-fg')}
              >{s}</button>
            ))}
          </div>
          <select aria-label="Company" value={company} onChange={e => set('company', e.target.value)} className={filterCls}>
            <option value="all">All companies</option>
            {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select aria-label="Platform" value={platform} onChange={e => set('platform', e.target.value)} className={filterCls}>
            <option value="all">All platforms</option>
            {(Object.keys(PLATFORM_LABEL) as Platform[]).map(p => <option key={p} value={p}>{PLATFORM_LABEL[p]}</option>)}
          </select>
          <select aria-label="Status" value={status} onChange={e => set('status', e.target.value)} className={filterCls}>
            {Object.entries(STATUSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          {filtered && <Button variant="ghost" onClick={() => setQ({})}><ArrowCounterClockwise size={16} />Reset</Button>}
        </div>

        {list.length === 0 ? (
          <div className="px-4 py-12 text-center">
            <p className="font-medium">No mentions match these filters</p>
            {filtered && <Button className="mt-3" onClick={() => setQ({})}>Reset filters</Button>}
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {list.map(p => (
              <li key={p.id} className={cx('flex gap-3 p-4', p.status !== 'new' && 'opacity-70')}>
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-subtle text-fg-2"><PlatformIcon p={p.platform} size={16} /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="truncate font-semibold">{nameOf(p.companyId)}</span>
                    <span className="truncate text-xs text-fg-3">{p.handle}</span>
                    <span aria-hidden className="text-xs text-fg-3">·</span>
                    <time className="shrink-0 text-xs text-fg-3" dateTime={new Date(p.at).toISOString()} title={new Date(p.at).toLocaleString()}>{timeAgo(p.at)}</time>
                  </div>
                  <p className="mt-1 text-[15px] leading-6">{p.text}</p>
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
                  {actionable(p) && <Button variant="ghost" className="w-9 px-0" aria-label="Dismiss" title="Dismiss" onClick={() => setPostStatus(p.id, 'dismissed')}><Archive size={16} /></Button>}
                  <a
                    href={sourceUrl(p)}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Open source"
                    title="Open source"
                    className="inline-flex size-9 items-center justify-center rounded-control text-fg-2 transition-colors duration-150 hover:bg-subtle hover:text-fg"
                  ><ArrowSquareOut size={16} /></a>
                  {actionable(p) && <Button className="ml-1" onClick={() => set('respond', p.id)}>Counter-post</Button>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Dialog wide open={!!responding && !!respondingCompany} onClose={() => set('respond', null)} title="Create counter-post">
        {responding && respondingCompany && (
          <CounterPost
            key={responding.id}
            post={responding}
            company={respondingCompany}
            onDone={() => { setPostStatus(responding.id, 'responded'); set('respond', null) }}
          />
        )}
      </Dialog>
    </div>
  )
}
