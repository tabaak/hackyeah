import { useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Link, useSearchParams } from 'react-router-dom'
import { mentionSeries, PLATFORM_LABEL, RANGES, type Range, VERDICT_LABEL, type Platform, type Severity, type Verdict } from '../lib/mock'
import { useStore } from '../lib/store'
import { compact, cx, PageActions, PlatformIcon, VerdictBadge } from '../lib/ui'

// Severity is a status scale (validated with dataviz/validate_palette.js); low stays neutral on purpose.
const SEV = {
  light: { low: '#6b7fa8', medium: '#d97706', high: '#b91c1c', grid: 'var(--border)', axis: 'var(--text-muted)', surface: 'var(--surface)' },
  dark: { low: '#7083ad', medium: '#e0a106', high: '#ef4444', grid: 'var(--border)', axis: 'var(--text-muted)', surface: 'var(--surface)' },
}
const SEVS: Severity[] = ['high', 'medium', 'low']
const SEV_LABEL: Record<Severity, string> = { high: 'High', medium: 'Medium', low: 'Low' }

// Shared recharts styling so every chart reads as one system
const tick = (c: typeof SEV.light) => ({ fill: c.axis, fontSize: 12 })
const tip = (c: typeof SEV.light) => ({
  cursor: { fill: c.grid, opacity: 0.5 },
  contentStyle: { background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 8, fontSize: 13 },
  labelStyle: { color: c.axis },
  itemStyle: { color: 'var(--text)' },
})

function Panel({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-panel border border-line bg-surface p-4">
      <h2 className="text-base font-semibold">{title}</h2>
      {sub && <p className="mb-4 text-xs text-fg-3">{sub}</p>}
      {children}
    </section>
  )
}

export default function Analytics() {
  const { posts: allPosts, companies, theme } = useStore()
  const c = SEV[theme === 'light' ? 'light' : 'dark']
  const [q, setQ] = useSearchParams()
  const raw = q.get('range')
  const range: Range = raw && raw in RANGES ? (raw as Range) : '24h'
  const { label: rangeLabel, ms } = RANGES[range]
  const [now] = useState(Date.now)
  const since = now - ms
  const posts = allPosts.filter(p => p.at >= since)
  const series = mentionSeries(companies, range)
  const per = range === '24h' ? 'hourly' : 'daily'
  const tickEvery = range === '30d' ? 4 : range === '7d' ? 0 : 3
  const total = series.reduce((s, h) => s + h.low + h.medium + h.high, 0)
  const openHigh = posts.filter(p => p.severity === 'high' && p.status === 'new').length
  const responded = posts.filter(p => p.status === 'responded').length
  const coordinated = posts.filter(p => p.cluster).length

  const byPlatform = (Object.keys(PLATFORM_LABEL) as Platform[])
    .map(p => ({ p, n: posts.filter(x => x.platform === p).length, reach: posts.filter(x => x.platform === p).reduce((s, x) => s + x.reach, 0) }))
    .sort((a, b) => b.reach - a.reach)
  const maxReach = Math.max(1, ...byPlatform.map(x => x.reach))

  const verdicts = (Object.keys(VERDICT_LABEL) as Verdict[]).map(v => ({ v, n: posts.filter(p => p.verdict === v && p.severity !== 'low').length }))

  const mix = SEVS.map(k => ({ k, n: series.reduce((s, h) => s + h[k], 0) }))
  const highShare = series.map(h => ({ label: h.label, share: Math.round((h.high / Math.max(1, h.low + h.medium + h.high)) * 100) }))
  const totalReach = posts.reduce((s, p) => s + p.reach, 0)
  const injections = posts.filter(p => p.injection).length

  const heat = byPlatform.map(x => ({ p: x.p, cells: SEVS.map(k => posts.filter(y => y.platform === x.p && y.severity === k).length) }))
  const maxHeat = Math.max(1, ...heat.flatMap(r => r.cells))

  const byCompany = companies
    .map(co => ({ name: co.name, n: posts.filter(p => p.companyId === co.id).length }))
    .sort((a, b) => b.n - a.n)
  const maxCompany = Math.max(1, ...byCompany.map(x => x.n))

  const statuses = [
    { label: 'Awaiting review', n: posts.filter(p => p.status === 'new').length, color: c.low },
    { label: 'Responded', n: responded, color: 'var(--accent)' },
    { label: 'Dismissed', n: posts.filter(p => p.status === 'dismissed').length, color: 'var(--border)' },
  ]
  const statusTotal = Math.max(1, posts.length)

  const metrics = [
    { label: `Mentions in ${rangeLabel}`, value: compact(total) },
    { label: 'Open high priority', value: openHigh, to: '/app/feed?severity=high' },
    { label: 'Coordinated clusters', value: coordinated },
    { label: 'Responses approved', value: responded },
    { label: 'Tracked reach', value: compact(totalReach) },
    { label: 'Injections blocked', value: injections },
    { label: 'Median time to draft', value: '4 min' },
  ]

  return (
    <div className="motion-page space-y-6">
      <PageActions>
        <div role="group" aria-label="Time range" className="flex w-fit rounded-control border border-line bg-surface p-0.5">
          {(Object.keys(RANGES) as Range[]).map(r => (
            <button
              key={r}
              aria-pressed={range === r}
              onClick={() => setQ(prev => { const n = new URLSearchParams(prev); if (r === '24h') n.delete('range'); else n.set('range', r); return n })}
              className={cx('h-8 cursor-pointer rounded-[4px] px-3 text-sm motion-control', range === r ? 'bg-selected font-medium text-fg' : 'text-fg-2 hover:text-fg')}
            >{RANGES[r].label}</button>
          ))}
        </div>
      </PageActions>

      {/* One metric strip with dividers (DESIGN §3.4) */}
      <dl className="grid grid-cols-2 divide-line rounded-panel border border-line bg-surface sm:grid-cols-4 xl:grid-cols-7 xl:divide-x">
        {metrics.map(m => (
          <div key={m.label} className="p-4">
            <dt className="text-xs text-fg-3">{m.label}</dt>
            <dd className="mt-1 text-2xl font-semibold">
              {m.to ? <Link to={m.to} className="motion-control hover:text-accent">{m.value}</Link> : m.value}
            </dd>
          </div>
        ))}
      </dl>

      <Panel title="Mentions by priority" sub={`Last ${rangeLabel} for ${companies.map(x => x.name).join(', ')}`}>
        <div className="h-72" role="img" aria-label={`Stacked bar chart of ${per} mentions by priority; the most recent buckets show a growing burst of high-priority posts.`}>
          <ResponsiveContainer>
            <BarChart data={series} margin={{ left: -16, right: 8 }}>
              <CartesianGrid vertical={false} stroke={c.grid} />
              <XAxis dataKey="label" tick={tick(c)} tickLine={false} axisLine={{ stroke: c.grid }} interval={tickEvery} />
              <YAxis tick={tick(c)} tickLine={false} axisLine={false} />
              <Tooltip {...tip(c)} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 13 }} formatter={v => <span style={{ color: c.axis }}>{v}</span>} />
              <Bar isAnimationActive={false} dataKey="low" name="Low" stackId="s" fill={c.low} stroke={c.surface} strokeWidth={1} />
              <Bar isAnimationActive={false} dataKey="medium" name="Medium" stackId="s" fill={c.medium} stroke={c.surface} strokeWidth={1} />
              <Bar isAnimationActive={false} dataKey="high" name="High" stackId="s" fill={c.high} stroke={c.surface} strokeWidth={1} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Priority mix" sub={`Share of all mentions in the last ${rangeLabel}`}>
          <div className="relative h-56" role="img" aria-label={`Donut chart: ${mix.map(m => `${SEV_LABEL[m.k]} ${m.n}`).join(', ')}`}>
            <ResponsiveContainer>
              <PieChart>
                <Pie isAnimationActive={false} data={mix} dataKey="n" nameKey="k" innerRadius="62%" outerRadius="88%" paddingAngle={2} stroke={c.surface} strokeWidth={2} cornerRadius={4}>
                  {mix.map(m => <Cell key={m.k} fill={c[m.k]} />)}
                </Pie>
                <Tooltip {...tip(c)} formatter={(v, k) => [v, SEV_LABEL[k as Severity]]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-semibold">{compact(total)}</span>
              <span className="text-xs text-fg-3">mentions</span>
            </div>
          </div>
          <ul className="mt-3 flex justify-center gap-4 text-xs text-fg-2">
            {mix.map(m => (
              <li key={m.k} className="flex items-center gap-1.5">
                <span className="size-2 rounded-full" style={{ background: c[m.k] }} />
                {SEV_LABEL[m.k]} <span className="font-mono">{Math.round((m.n / Math.max(1, total)) * 100)}%</span>
              </li>
            ))}
          </ul>
        </Panel>

        <div className="lg:col-span-2">
          <Panel title="High-priority share" sub={`Percent of ${per} mentions rated high in the last ${rangeLabel}`}>
            <div className="h-64" role="img" aria-label={`Area chart of the ${per} high-priority share; it climbs sharply at the end of the range.`}>
              <ResponsiveContainer>
                <AreaChart data={highShare} margin={{ left: -16, right: 8 }}>
                  <defs>
                    <linearGradient id="hs" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={c.high} stopOpacity={0.28} />
                      <stop offset="100%" stopColor={c.high} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke={c.grid} />
                  <XAxis dataKey="label" tick={tick(c)} tickLine={false} axisLine={{ stroke: c.grid }} interval={tickEvery} />
                  <YAxis tick={tick(c)} tickLine={false} axisLine={false} unit="%" />
                  <Tooltip {...tip(c)} cursor={{ stroke: c.axis, strokeDasharray: '3 3' }} formatter={v => [`${v}%`, 'High priority']} />
                  <Area isAnimationActive={false} type="monotone" dataKey="share" stroke={c.high} strokeWidth={2} fill="url(#hs)" activeDot={{ r: 4, stroke: c.surface, strokeWidth: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Reach by platform" sub="Estimated views of tracked mentions">
          <ul className="space-y-3">
            {byPlatform.map(x => (
              <li key={x.p} className="grid grid-cols-[110px_1fr_56px] items-center gap-3 text-sm">
                <span className="flex items-center gap-2 text-fg-2"><PlatformIcon p={x.p} />{PLATFORM_LABEL[x.p]}</span>
                <span className="h-2 rounded-full bg-subtle" title={`${x.n} mentions`}>
                  <span className="block h-2 rounded-full bg-accent" style={{ width: `${(x.reach / maxReach) * 100}%` }} />
                </span>
                <span className="text-right font-mono text-xs text-fg-2">{compact(x.reach)}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Platform × priority" sub="Where the riskiest mentions come from">
          <table className="w-full border-separate border-spacing-1 text-sm">
            <thead>
              <tr className="text-xs text-fg-3">
                <th />
                {SEVS.map(k => <th key={k} className="font-normal">{SEV_LABEL[k]}</th>)}
              </tr>
            </thead>
            <tbody>
              {heat.map(r => (
                <tr key={r.p}>
                  <th className="pr-2 text-left font-normal text-fg-2"><span className="flex items-center gap-2"><PlatformIcon p={r.p} />{PLATFORM_LABEL[r.p]}</span></th>
                  {r.cells.map((n, i) => (
                    <td key={i} className="relative h-9 rounded-md bg-subtle text-center font-mono text-xs" title={`${SEV_LABEL[SEVS[i]]} on ${PLATFORM_LABEL[r.p]}: ${n}`}>
                      <span className="absolute inset-0 rounded-md" style={{ background: c[SEVS[i]], opacity: n ? 0.15 + (n / maxHeat) * 0.65 : 0 }} />
                      <span className="relative">{n}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Claim verification" sub="Medium and high priority mentions, checked against your documents">
          <ul className="divide-y divide-line">
            {verdicts.map(x => (
              <li key={x.v} className="flex items-center justify-between py-2.5">
                <VerdictBadge v={x.v} />
                <span className="font-mono text-sm">{x.n}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-fg-3">Priority and verification are separate: a supported claim can still need a response.</p>
        </Panel>

        <Panel title="Response pipeline" sub="What happened to tracked mentions">
          <div className="flex h-3 gap-0.5 overflow-hidden rounded-full" role="img" aria-label={statuses.map(x => `${x.label} ${x.n}`).join(', ')}>
            {statuses.filter(x => x.n).map(x => (
              <span key={x.label} title={`${x.label}: ${x.n}`} style={{ width: `${(x.n / statusTotal) * 100}%`, background: x.color }} />
            ))}
          </div>
          <ul className="mt-3 divide-y divide-line">
            {statuses.map(x => (
              <li key={x.label} className="flex items-center justify-between py-2.5 text-sm">
                <span className="flex items-center gap-2 text-fg-2"><span className="size-2 rounded-full" style={{ background: x.color }} />{x.label}</span>
                <span className="font-mono">{x.n}</span>
              </li>
            ))}
          </ul>

          <h3 className="mt-5 mb-2 text-xs text-fg-3">Mentions by company</h3>
          <ul className="space-y-3">
            {byCompany.map(x => (
              <li key={x.name} className="grid grid-cols-[110px_1fr_56px] items-center gap-3 text-sm">
                <span className="truncate text-fg-2" title={x.name}>{x.name}</span>
                <span className="h-2 rounded-full bg-subtle">
                  <span className="block h-2 rounded-full bg-accent" style={{ width: `${(x.n / maxCompany) * 100}%` }} />
                </span>
                <span className="text-right font-mono text-xs text-fg-2">{x.n}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  )
}
