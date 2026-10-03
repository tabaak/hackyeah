import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Link } from 'react-router-dom'
import { hourlySeries, PLATFORM_LABEL, VERDICT_LABEL, type Platform, type Verdict } from '../lib/mock'
import { useStore } from '../lib/store'
import { compact, PlatformIcon, VerdictBadge } from '../lib/ui'

// Severity is a status scale (validated with dataviz/validate_palette.js); low stays neutral on purpose.
const SEV = {
  light: { low: '#6b7fa8', medium: '#d97706', high: '#b91c1c', grid: 'var(--border)', axis: 'var(--text-muted)', surface: 'var(--surface)' },
  dark: { low: '#7083ad', medium: '#e0a106', high: '#ef4444', grid: 'var(--border)', axis: 'var(--text-muted)', surface: 'var(--surface)' },
}

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
  const { posts, companies, theme } = useStore()
  const c = SEV[theme === 'light' ? 'light' : 'dark']
  const series = hourlySeries(companies)
  const total = series.reduce((s, h) => s + h.low + h.medium + h.high, 0)
  const openHigh = posts.filter(p => p.severity === 'high' && p.status === 'new').length
  const responded = posts.filter(p => p.status === 'responded').length
  const coordinated = posts.filter(p => p.cluster).length

  const byPlatform = (Object.keys(PLATFORM_LABEL) as Platform[])
    .map(p => ({ p, n: posts.filter(x => x.platform === p).length, reach: posts.filter(x => x.platform === p).reduce((s, x) => s + x.reach, 0) }))
    .sort((a, b) => b.reach - a.reach)
  const maxReach = Math.max(1, ...byPlatform.map(x => x.reach))

  const verdicts = (Object.keys(VERDICT_LABEL) as Verdict[]).map(v => ({ v, n: posts.filter(p => p.verdict === v && p.severity !== 'low').length }))

  const metrics = [
    { label: 'Mentions · 24h', value: compact(total) },
    { label: 'High priority · open', value: openHigh, to: '/app/feed?severity=high' },
    { label: 'Coordinated clusters', value: coordinated },
    { label: 'Responses approved', value: responded },
    { label: 'Median time to draft', value: '4 min' },
  ]

  return (
    <div className="space-y-6">
      {/* One metric strip with dividers (DESIGN §3.4) */}
      <dl className="grid grid-cols-2 divide-line rounded-panel border border-line bg-surface sm:grid-cols-3 lg:grid-cols-5 lg:divide-x">
        {metrics.map(m => (
          <div key={m.label} className="p-4">
            <dt className="text-xs text-fg-3">{m.label}</dt>
            <dd className="mt-1 text-2xl font-semibold">
              {m.to ? <Link to={m.to} className="hover:text-accent">{m.value}</Link> : m.value}
            </dd>
          </div>
        ))}
      </dl>

      <Panel title="Mentions by priority" sub={`Last 24 hours · ${companies.map(x => x.name).join(', ')}`}>
        <div className="h-72" role="img" aria-label="Stacked bar chart of hourly mentions by priority; the last five hours show a growing burst of high-priority posts.">
          <ResponsiveContainer>
            <BarChart data={series} margin={{ left: -16, right: 8 }}>
              <CartesianGrid vertical={false} stroke={c.grid} />
              <XAxis dataKey="hour" tick={{ fill: c.axis, fontSize: 12 }} tickLine={false} axisLine={{ stroke: c.grid }} interval={3} />
              <YAxis tick={{ fill: c.axis, fontSize: 12 }} tickLine={false} axisLine={false} />
              <Tooltip
                cursor={{ fill: c.grid, opacity: 0.5 }}
                contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 8, fontSize: 13 }}
                labelStyle={{ color: c.axis }}
                itemStyle={{ color: 'var(--text)' }}
              />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 13 }} formatter={v => <span style={{ color: c.axis }}>{v}</span>} />
              <Bar dataKey="low" name="Low" stackId="s" fill={c.low} stroke={c.surface} strokeWidth={1} />
              <Bar dataKey="medium" name="Medium" stackId="s" fill={c.medium} stroke={c.surface} strokeWidth={1} />
              <Bar dataKey="high" name="High" stackId="s" fill={c.high} stroke={c.surface} strokeWidth={1} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

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
      </div>
    </div>
  )
}
