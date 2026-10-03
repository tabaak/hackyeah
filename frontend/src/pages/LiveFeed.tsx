import { Archive, Lightning, UsersThree, Warning } from '@phosphor-icons/react'
import { useSearchParams } from 'react-router-dom'
import { CounterPost } from '../components/CounterPost'
import { PostRow } from '../components/PostRow'
import { PLATFORM_LABEL, type Platform, type Post } from '../lib/mock'
import { useStore } from '../lib/store'
import { Badge, Button, compact, cx, Dialog, PlatformIcon, timeAgo } from '../lib/ui'

// Matches the severity segmented control
const filterCls = 'h-[38px] min-w-0 flex-1 cursor-pointer sm:flex-none rounded-control border border-line bg-surface px-3 text-sm text-fg-2 motion-control hover:text-fg focus:outline-none focus-visible:border-accent'

const SEVERITIES = ['all', 'high', 'medium', 'low'] as const
const STATUSES = { open: 'Open', archive: 'Archive', responded: 'Responded', dismissed: 'Dismissed', all: 'All' } as const

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

  const list = posts.filter(p =>
    (company === 'all' || p.companyId === company) &&
    (severity === 'all' || p.severity === severity) &&
    (platform === 'all' || p.platform === platform) &&
    (status === 'all' || (status === 'open' ? p.status === 'new' : status === 'archive' ? p.status !== 'new' : p.status === status)),
  )
  const filtered = q.has('company') || q.has('severity') || q.has('platform') || q.has('status')

  return (
    <div className="motion-page space-y-6">
      {urgent.length > 0 && (
        <section aria-labelledby="urgent-h">
          <div className="mb-3 flex items-center gap-2">
            <Warning size={20} weight="fill" className="text-danger" />
            <h2 id="urgent-h" className="text-lg font-semibold">Needs attention <span className="font-mono text-sm font-normal text-fg-3">{urgent.length}</span></h2>
          </div>
          <div className="-mx-4 flex snap-x snap-mandatory scroll-px-4 gap-3 overflow-x-auto px-4 pb-4 md:-mx-6 md:scroll-px-6 md:px-6">
            {urgent.map(p => (
              <article key={p.id} className="flex w-[min(340px,85vw)] shrink-0 snap-start flex-col gap-3 rounded-panel border border-danger/40 bg-surface p-4">
                <div className="flex gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-subtle text-fg-2"><PlatformIcon p={p.platform} size={16} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="truncate font-semibold">{nameOf(p.companyId)}</span>
                      <span className="truncate text-xs text-fg-3">{p.handle}</span>
                      <time className="ml-auto shrink-0 text-xs text-fg-3" dateTime={new Date(p.at).toISOString()} title={new Date(p.at).toLocaleString()}>{timeAgo(p.at)}</time>
                    </div>
                    <p className="mt-1 line-clamp-2 text-[15px] leading-6">{p.text}</p>
                  </div>
                </div>

                <div className="rounded-control bg-subtle px-3 py-2" title={p.reason}>
                  <p className="line-clamp-2 text-sm text-fg-2">{p.reason}</p>
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-fg-3">
                  {p.injection && <Badge tone="danger"><Warning size={14} weight="bold" />AI manipulation</Badge>}
                  <span className="flex items-center gap-1"><Lightning size={14} /><span className="font-mono text-fg-2">{compact(p.reach)}</span> reach</span>
                  {p.cluster && <span className="flex items-center gap-1"><UsersThree size={14} /><span className="font-mono text-fg-2">{p.cluster.size}</span> similar</span>}
                </div>

                <div className="mt-auto flex gap-2">
                  <Button variant="primary" className="flex-1" onClick={() => set('respond', p.id)}>Create counter-post</Button>
                  <Button variant="ghost" className="w-9 px-0" aria-label="Dismiss" title="Dismiss" onClick={() => setPostStatus(p.id, 'dismissed')}><Archive size={16} /></Button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section aria-labelledby="feed-h" className="rounded-panel border border-line bg-surface max-sm:-mx-4 max-sm:rounded-none max-sm:border-x-0">
        <div className="flex flex-wrap items-center gap-3 rounded-t-panel border-b max-sm:rounded-none border-line bg-surface p-4 lg:sticky lg:top-0 lg:z-10">
          <h2 id="feed-h" className="mr-auto text-lg font-semibold">All mentions <span className="font-mono text-sm font-normal text-fg-3">{list.length}</span></h2>
          <div role="group" aria-label="Severity" className="flex w-full rounded-control border border-line p-0.5 sm:w-auto">
            {SEVERITIES.map(s => (
              <button
                key={s}
                aria-pressed={severity === s}
                onClick={() => set('severity', s)}
                className={cx('h-8 flex-1 cursor-pointer rounded-[4px] px-3 text-sm capitalize motion-control', severity === s ? 'bg-selected font-medium text-fg' : 'text-fg-2 hover:text-fg')}
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
          {filtered && <Button variant="ghost" onClick={() => setQ({})}>Reset</Button>}
        </div>

        {list.length === 0 ? (
          <div className="px-4 py-12 text-center">
            <p className="font-medium">No mentions match these filters</p>
            {filtered && <Button className="mt-3" onClick={() => setQ({})}>Reset filters</Button>}
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {list.map(p => (
              <PostRow
                key={p.id}
                post={p}
                companyName={nameOf(p.companyId)}
                actionable={actionable(p)}
                onDismiss={() => setPostStatus(p.id, 'dismissed')}
                onRespond={() => set('respond', p.id)}
              />
            ))}
          </ul>
        )}
      </section>

      <Dialog wide open={!!responding && !!respondingCompany} onClose={() => set('respond', null)} title="Create counter-post">
        {responding && respondingCompany && (
          <CounterPost
            key={responding.id}
            post={responding}
            onDone={() => set('respond', null)}
          />
        )}
      </Dialog>
    </div>
  )
}
