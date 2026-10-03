import { Check, FileText, ShieldWarning, Warning } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { PLATFORM_LABEL, type Classification, type Company, type Post, type Verdict } from '../lib/mock'
import { useStore } from '../lib/store'
import { Badge, Button, ClassBadge, compact, inputCls, cx, PlatformIcon, timeAgo, VerdictBadge } from '../lib/ui'

// GET /mentions/{id}/response: claim check, evidence, draft, disclosure check and approval state
type MentionResponse = {
  claimCheck: { verdict: Verdict; reason: string }
  evidence: { docId: string; name: string; classification: Classification }[]
  draft: string
  disclosure: { needsCompliance: boolean; reason: string }
  injectionBlocked: boolean
  approval: { state: 'none' | 'pending' | 'approved'; by: string | null; at: number | null }
}

export function CounterPost({ post, company, onDone }: { post: Post; company: Company; onDone: () => void }) {
  const { user, refreshFeed } = useStore()
  const [data, setData] = useState<MentionResponse | null>(null)
  const [text, setText] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  // The first open generates the draft on the server (LLM: can take a few seconds).
  useEffect(() => {
    const controller = new AbortController()
    api<MentionResponse>(`/mentions/${post.id}/response`, { signal: controller.signal })
      .then(r => { setData(r); setText(r.draft); setLoadError(null) })
      .catch((e: Error) => { if (!controller.signal.aborted) setLoadError(e.message) })
    return () => controller.abort()
  }, [post.id, attempt])

  const claim = data?.claimCheck ?? { verdict: post.verdict, reason: post.reason }
  const evidence = data?.evidence ?? []
  const needsCompliance = data?.disclosure.needsCompliance ?? false
  // Compliance users may approve directly; analysts must request approval when confidential documents are involved.
  const requestOnly = needsCompliance && user?.role !== 'compliance'
  const approval = data?.approval.state ?? 'none'

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* user can select manually */ }
  }

  // Saving re-runs the disclosure check and drops any earlier approval on the server.
  async function saveDraft(): Promise<MentionResponse | null> {
    if (!data || text === data.draft) return data
    const r = await api<MentionResponse>(`/mentions/${post.id}/response/draft`, { method: 'PATCH', body: JSON.stringify({ text }) })
    setData(r)
    return r
  }

  async function submit() {
    setBusy(true)
    setActionError(null)
    try {
      const current = await saveDraft()
      if (!current) return
      const request = current.disclosure.needsCompliance && user?.role !== 'compliance'
      await api(`/mentions/${post.id}/response/${request ? 'request-approval' : 'approve'}`, { method: 'POST' })
      await refreshFeed()
      onDone()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setBusy(false)
    }
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
          <VerdictBadge v={claim.verdict} />
          <p className="text-sm text-fg-2">{claim.reason}</p>
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Evidence used</h3>
          {data && evidence.length === 0 ? (
            <p className="rounded-panel bg-warning-bg p-3 text-sm text-warning">
              No documents uploaded for {company.name}. The draft avoids factual claims — add documents in Companies.
            </p>
          ) : (
            <ul className="space-y-2">
              {evidence.map(d => (
                <li key={d.docId} className="flex items-center gap-2 rounded-control border-l-2 border-accent bg-subtle px-3 py-2 text-sm">
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
          onBlur={() => { saveDraft().catch((e: Error) => setActionError(e.message)) }}
          disabled={!data}
          placeholder={loadError ? '' : 'Generating draft…'}
          aria-label="Counter-post text"
          className={cx(inputCls, 'h-auto w-full min-h-[240px] resize-y py-2 text-[15px] leading-6')}
        />
        <div className="text-right font-mono text-xs text-fg-3">{text.length} chars</div>
        {data && (
          <div className={cx('flex gap-2 rounded-panel p-3 text-sm', needsCompliance ? 'bg-warning-bg text-warning' : 'bg-success-bg text-success')}>
            {needsCompliance ? <ShieldWarning size={18} className="shrink-0" /> : <Check size={18} className="shrink-0" />}
            <span>
              {needsCompliance
                ? 'Disclosure check: relies on a confidential document. Compliance must approve before publishing.'
                : 'Disclosure check: no confidential details found. Analyst approval is enough.'}
            </span>
          </div>
        )}
        {(data?.injectionBlocked ?? post.injection) && (
          <div className="flex gap-2 rounded-panel bg-danger-bg p-3 text-sm text-danger">
            <Warning size={18} className="shrink-0" />
            Attempted AI manipulation in this cluster was blocked — the hidden instruction was not followed.
          </div>
        )}
        {(loadError || actionError) && (
          <p role="alert" className="text-sm text-danger">{loadError ?? actionError}</p>
        )}
        <div className="mt-auto flex flex-wrap justify-end gap-2 pt-2">
          {loadError && <Button onClick={() => setAttempt(n => n + 1)}>Retry</Button>}
          <Button onClick={copy} disabled={!data}>{copied ? 'Copied' : 'Copy'}</Button>
          <Button variant="primary" onClick={submit} disabled={!data || busy || approval !== 'none'}>
            {approval === 'approved' ? 'Approved' : approval === 'pending' ? 'Approval requested' : requestOnly ? 'Request approval' : 'Approve response'}
          </Button>
        </div>
      </section>
    </div>
  )
}
