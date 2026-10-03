import { Check, FileText, ShieldWarning, Warning } from '@phosphor-icons/react'
import { useState } from 'react'
import { PLATFORM_LABEL, type Company, type Post } from '../lib/mock'
import { Badge, Button, ClassBadge, compact, inputCls, cx, PlatformIcon, timeAgo, VerdictBadge } from '../lib/ui'

function draftFor(p: Post, c: Company) {
  const site = c.website || `the official ${c.name} channels`
  switch (p.verdict) {
    case 'contradicted_by_documents':
      return `We've seen posts claiming that ${c.name} has stopped services or lost customer data. This is not accurate. According to our records, all accounts, cards and transfers are operating normally. A small number of ATMs in one region were briefly offline for scheduled maintenance this morning and are back in service.\n\nPlease rely on verified updates at ${site}.`
    case 'supported_by_documents':
      return `Yes — our app had an outage yesterday that lasted about 2 hours 40 minutes. We're sorry for the disruption. Payments made during that time have been processed, and we're publishing a full incident report at ${site}.`
    case 'insufficient_evidence':
      return `We're aware of claims circulating about ${c.name}. We are checking them and will share verified information at ${site}. Please treat unconfirmed reports with caution.`
    default:
      return `Thanks for sharing your view. We take feedback seriously — if you'd like to talk to our team directly, reach us via ${site}.`
  }
}

export function CounterPost({ post, company, onDone }: { post: Post; company: Company; onDone: () => void }) {
  const [text, setText] = useState(() => draftFor(post, company))
  const [copied, setCopied] = useState(false)
  const evidence = company.documents.filter(d => d.classification !== 'restricted').slice(0, 3)
  const needsCompliance = evidence.some(d => d.classification === 'confidential')

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* user can select manually */ }
  }

  return (
    <div className="grid gap-5 md:grid-cols-[1fr_1.2fr]">
      <section className="space-y-4">
        <div className="rounded-panel border border-line p-3">
          <div className="mb-2 flex items-center gap-2 text-xs text-fg-3">
            <PlatformIcon p={post.platform} size={14} />
            {PLATFORM_LABEL[post.platform]} · {post.handle} · {timeAgo(post.at)}
          </div>
          <p className="text-[15px] leading-6">{post.text}</p>
          <div className="mt-2 text-xs text-fg-3">Reach ≈ {compact(post.reach)}</div>
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Claim check</h3>
          <VerdictBadge v={post.verdict} />
          <p className="text-sm text-fg-2">{post.reason}</p>
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Evidence used</h3>
          {evidence.length === 0 ? (
            <p className="rounded-panel bg-warning-bg p-3 text-sm text-warning">
              No documents uploaded for {company.name}. The draft avoids factual claims — add documents in Companies.
            </p>
          ) : (
            <ul className="space-y-2">
              {evidence.map(d => (
                <li key={d.id} className="flex items-center gap-2 rounded-control border-l-2 border-accent bg-subtle px-3 py-2 text-sm">
                  <FileText size={16} className="shrink-0 text-fg-3" />
                  <span className="min-w-0 flex-1 truncate">{d.name}</span>
                  <ClassBadge c={d.classification} />
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-fg-3">This assessment is based on the documents provided.</p>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Counter-post draft</h3>
          <Badge>AI draft</Badge>
        </div>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          aria-label="Counter-post text"
          className={cx(inputCls, 'h-auto w-full min-h-[240px] resize-y py-2 text-[15px] leading-6')}
        />
        <div className="text-right font-mono text-xs text-fg-3">{text.length} chars</div>
        <div className={cx('flex gap-2 rounded-panel p-3 text-sm', needsCompliance ? 'bg-warning-bg text-warning' : 'bg-success-bg text-success')}>
          {needsCompliance ? <ShieldWarning size={18} className="shrink-0" /> : <Check size={18} className="shrink-0" />}
          <span>
            {needsCompliance
              ? 'Disclosure check: relies on a confidential document. Compliance must approve before publishing.'
              : 'Disclosure check: no confidential details found. Analyst approval is enough.'}
          </span>
        </div>
        {post.injection && (
          <div className="flex gap-2 rounded-panel bg-danger-bg p-3 text-sm text-danger">
            <Warning size={18} className="shrink-0" />
            Attempted AI manipulation in this cluster was blocked — the hidden instruction was not followed.
          </div>
        )}
        <div className="mt-auto flex flex-wrap justify-end gap-2 pt-2">
          <Button onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
          <Button variant="primary" onClick={onDone}>{needsCompliance ? 'Request approval' : 'Approve response'}</Button>
        </div>
      </section>
    </div>
  )
}
