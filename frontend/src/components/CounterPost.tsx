import { Sparkle } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { VERDICT_LABEL, type Classification, type Post, type Verdict } from '../lib/mock'
import { useStore } from '../lib/store'
import { Button, cx, Field, inputCls, PlatformIcon, timeAgo } from '../lib/ui'

// GET /mentions/{id}/response: claim check, evidence, draft, disclosure check and approval state
type MentionResponse = {
  claimCheck: { verdict: Verdict; reason: string }
  evidence: { docId: string; name: string; classification: Classification }[]
  draft: string
  disclosure: { needsCompliance: boolean; reason: string }
  injectionBlocked: boolean
  approval: { state: 'none' | 'pending' | 'approved'; by: string | null; at: number | null }
}

// One-click rewrites; the label is what the user sees, the instruction is what the model gets.
const PRESETS = [
  ['Shorter', 'Make it shorter and tighter, keep the main point.'],
  ['More formal', 'Use a more formal, corporate tone.'],
  ['Warmer', 'Make it warmer and more empathetic to worried readers.'],
  ['Lead with facts', 'Open with the key verified fact, then the rest.'],
  ['Simpler', 'Use plain, simple words a general audience understands.'],
] as const

export function CounterPost({ post, onDone }: { post: Post; onDone: () => void }) {
  const { user, refreshFeed } = useStore()
  const [data, setData] = useState<MentionResponse | null>(null)
  const [text, setText] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [rewriting, setRewriting] = useState(false)

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

  // AI rewrite of the current (possibly unsaved) text; the server saves it like a manual edit.
  async function rewrite(instruction: string) {
    setRewriting(true)
    setActionError(null)
    try {
      const r = await api<MentionResponse>(`/mentions/${post.id}/response/revise`, { method: 'POST', body: JSON.stringify({ text, instruction }) })
      setData(r)
      setText(r.draft)
      setInstruction(typed => (typed === instruction ? '' : typed))
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setRewriting(false)
    }
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

  const sources = evidence.map(d => d.name).join(', ')

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-5 md:grid-cols-2">
        {/* Grid rows stretch: the quote grows so both columns end at the same line */}
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Original post</h3>
          <blockquote className="flex-1 border-l-2 border-line pl-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-fg-3">
              <PlatformIcon p={post.platform} size={14} />
              {post.handle} · {timeAgo(post.at)}
            </div>
            <p className="text-[15px] leading-6 text-fg-2">{post.text}</p>
          </blockquote>
          <p className="rounded-panel bg-subtle p-3 text-sm text-fg-2">
            <span className="font-medium text-fg">{VERDICT_LABEL[claim.verdict]}.</span> {claim.reason}
          </p>
        </section>

        <div className="space-y-3">
          <Field label="Counter-post" hint={sources ? `Based on ${sources}` : undefined}>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              onBlur={() => { saveDraft().catch((e: Error) => setActionError(e.message)) }}
              disabled={!data || rewriting}
              placeholder={loadError ? '' : 'Writing a draft…'}
              className={cx(inputCls, 'h-auto w-full min-h-[200px] resize-y py-2.5 text-[15px] leading-6')}
            />
          </Field>
          <form onSubmit={e => { e.preventDefault(); rewrite(instruction) }} className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map(([label, preset]) => (
                <Button key={label} type="button" className="h-8 px-2.5" disabled={!data || rewriting} onClick={() => rewrite(preset)}>
                  {label}
                </Button>
              ))}
            </div>
            <textarea
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              // Enter sends, Shift+Enter adds a line
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }}
              disabled={!data || rewriting}
              maxLength={500}
              rows={3}
              placeholder="Or describe the change: mention the new hotline, sound less defensive…"
              aria-label="What should AI change in the counter-post"
              className={cx(inputCls, 'h-auto w-full resize-y py-2 text-sm leading-5')}
            />
            <div className="flex justify-end">
              <Button type="submit" disabled={!data || rewriting || !instruction.trim()}>
                <Sparkle size={16} />{rewriting ? 'Rewriting…' : 'Rewrite'}
              </Button>
            </div>
          </form>
        </div>
      </div>
      {needsCompliance && (
        <p className="text-sm text-warning">Uses a confidential document, so compliance must approve it.</p>
      )}
      {(loadError || actionError) && (
        <p role="alert" className="text-sm text-danger">{loadError ?? actionError}</p>
      )}

      <div className="flex justify-end gap-2">
        {loadError && <Button onClick={() => setAttempt(n => n + 1)}>Retry</Button>}
        <Button onClick={copy} disabled={!data}>{copied ? 'Copied' : 'Copy'}</Button>
        <Button variant="primary" onClick={submit} disabled={!data || busy || rewriting || approval !== 'none'}>
          {approval === 'approved' ? 'Approved' : approval === 'pending' ? 'Approval requested' : requestOnly ? 'Request approval' : 'Approve'}
        </Button>
      </div>
    </div>
  )
}
