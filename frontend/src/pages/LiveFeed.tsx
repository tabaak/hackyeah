import { Archive, ArrowCounterClockwise, Lightning, PencilSimpleLine, UsersThree, Warning } from '@phosphor-icons/react'
import { useSearchParams } from 'react-router-dom'
import { CounterPost } from '../components/CounterPost'
import { PLATFORM_LABEL, type Platform, type Post } from '../lib/mock'
import { useStore } from '../lib/store'
import { Badge, Button, compact, cx, Dialog, inputCls, PlatformIcon, SeverityBadge, timeAgo, VerdictBadge } from '../lib/ui'

const SEVERITIES = ['all', 'high', 'medium', 'low'] as const
const STATUSES = { open: 'Open', responded: 'Responded', dismissed: 'Dismissed', all: 'All' } as const

function PostMeta({ p, company }: { p: Post; company?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-3">
      <PlatformIcon p={p.platform} size={14} />
      <span>{PLATFORM_LABEL[p.platform]} · {p.handle}</span>
      <span aria-hidden>·</span>
      <span className="font-medium text-fg-2">{company}</span>
      <span aria-hidden>·</span>
      <time dateTime={new Date(p.at).toISOString()} title={new Date(p.at).toLocaleString()}>{timeAgo(p.at)}</time>
    </div>
  )
}

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
            <span className="text-sm text-fg-3">· highest-reach open threats</span>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {urgent.map(p => (
              <article key={p.id} className="flex flex-col rounded-panel border border-danger/40 bg-surface p-4">
                <div className="mb-2 flex items-center gap-2">
                  <SeverityBadge s={p.severity} />
                  {p.injection && <Badge tone="danger">AI manipulation attempt</Badge>}
                </div>
                <PostMeta p={p} company={nameOf(p.companyId)} />
                <p className="mt-2 line-clamp-3 text-[15px] leading-6">{p.text}</p>
                <p className="mt-2 line-clamp-2 text-sm text-fg-2">{p.reason}</p>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-fg-3">
                  <span className="flex items-center gap-1"><Lightning size={14} />Reach {compact(p.reach)}</span>
                  {p.cluster && <span className="flex items-center gap-1"><UsersThree size={14} />{p.cluster.size} posts · {p.cluster.accounts} accounts</span>}
                </div>
                <div className="mt-auto flex gap-2 pt-4">
                  <Button variant="primary" className="flex-1" onClick={() => set('respond', p.id)}>
                    <PencilSimpleLine size={16} />Create counter-post
                  </Button>
                  <Button variant="ghost" aria-label="Dismiss" onClick={() => setPostStatus(p.id, 'dismissed')}><Archive size={16} /></Button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section aria-labelledby="feed-h" className="rounded-panel border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
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
          <select aria-label="Company" value={company} onChange={e => set('company', e.target.value)} className={cx(inputCls, 'w-auto')}>
            <option value="all">All companies</option>
            {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select aria-label="Platform" value={platform} onChange={e => set('platform', e.target.value)} className={cx(inputCls, 'w-auto')}>
            <option value="all">All platforms</option>
            {(Object.keys(PLATFORM_LABEL) as Platform[]).map(p => <option key={p} value={p}>{PLATFORM_LABEL[p]}</option>)}
          </select>
          <select aria-label="Status" value={status} onChange={e => set('status', e.target.value)} className={cx(inputCls, 'w-auto')}>
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
              <li key={p.id} className={cx('grid gap-3 px-4 py-4 sm:grid-cols-[1fr_auto]', p.status !== 'new' && 'opacity-70')}>
                <div className="min-w-0 space-y-1.5">
                  <PostMeta p={p} company={nameOf(p.companyId)} />
                  <p className="text-[15px] leading-6">{p.text}</p>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <SeverityBadge s={p.severity} />
                    <VerdictBadge v={p.verdict} />
                    {p.cluster && <Badge><UsersThree size={14} />{p.cluster.size} similar</Badge>}
                    {p.status === 'responded' && <Badge tone="success">Responded</Badge>}
                    {p.status === 'dismissed' && <Badge><Archive size={14} />Dismissed</Badge>}
                    <span className="text-xs text-fg-3">Reach {compact(p.reach)}</span>
                  </div>
                </div>
                {p.status === 'new' && p.severity !== 'low' && (
                  <div className="flex items-start gap-2">
                    <Button onClick={() => set('respond', p.id)}><PencilSimpleLine size={16} />Counter-post</Button>
                    <Button variant="ghost" aria-label="Dismiss" onClick={() => setPostStatus(p.id, 'dismissed')}><Archive size={16} /></Button>
                  </div>
                )}
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
