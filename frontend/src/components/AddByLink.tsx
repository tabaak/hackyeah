import { LinkSimple } from '@phosphor-icons/react'
import { useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import type { Post } from '../lib/mock'
import { useStore } from '../lib/store'
import { Button, cx, Dialog, Field, inputCls, SeverityBadge, VerdictBadge } from '../lib/ui'

// Adds one post or article from its link right away: search indexing can take minutes, a link takes seconds.
export function AddByLink({ defaultCompany }: { defaultCompany?: string }) {
  const { posts, companies, refreshFeed } = useStore()
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [added, setAdded] = useState<{ post: Post; known: boolean } | null>(null)
  const company = companyId || (defaultCompany && defaultCompany !== 'all' ? defaultCompany : companies[0]?.id) || ''

  const close = () => { setOpen(false); setUrl(''); setError(null); setAdded(null) }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const post = await api<Post>('/mentions/import', { method: 'POST', body: JSON.stringify({ url: url.trim(), companyId: company }) })
      setAdded({ post, known: posts.some(p => p.id === post.id) })
      await refreshFeed()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)} disabled={!companies.length}><LinkSimple size={16} />Add by link</Button>
      <Dialog open={open} onClose={close} title="Add a post by link">
        {added ? (
          <div className="space-y-4">
            <p className="text-sm text-fg-2">{added.known ? 'Already in the feed.' : 'Added to the feed and analysed.'}</p>
            <div className="space-y-2 rounded-panel border border-line p-3">
              <p className="line-clamp-3 text-[15px] leading-6">{added.post.text}</p>
              <div className="flex flex-wrap gap-1.5"><SeverityBadge s={added.post.severity} /><VerdictBadge v={added.post.verdict} /></div>
              {added.post.reason && <p className="text-sm text-fg-2">{added.post.reason}</p>}
            </div>
            <div className="flex justify-end gap-2">
              <Button onClick={() => { setAdded(null); setUrl('') }}>Add another</Button>
              <Button variant="primary" onClick={close}>Done</Button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <Field label="Link" hint="An X post or a news article. Search can take minutes to index new posts; a link is read right away.">
              <input autoFocus required type="url" value={url} onChange={e => setUrl(e.target.value)}
                placeholder="https://x.com/…/status/…" className={cx(inputCls, 'w-full')} />
            </Field>
            {companies.length > 1 && (
              <Field label="Company">
                <select value={company} onChange={e => setCompanyId(e.target.value)} className={cx(inputCls, 'w-full')}>
                  {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </Field>
            )}
            {error && <p role="alert" className="text-sm text-danger">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={close}>Cancel</Button>
              <Button type="submit" variant="primary" disabled={busy || !url.trim() || !company}>{busy ? 'Reading and analysing…' : 'Add to feed'}</Button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  )
}
