import { FileText, Globe, Plus, Sparkle, UploadSimple } from '@phosphor-icons/react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CompanyWizard, DocsUpload, type PendingDoc } from '../components/CompanySetup'
import type { Classification, Company } from '../lib/mock'
import { useStore } from '../lib/store'
import { Badge, Button, ClassBadge, cx, Dialog, PageActions } from '../lib/ui'

// ponytail: canned summary from doc metadata; replace with the backend's corpus summary endpoint.
function summarize(c: Company) {
  const d = c.documents
  if (!d.length) return `No documents yet. Detection works, but counter-posts for ${c.name} will avoid factual claims until documents are added.`
  const count = (k: Classification) => d.filter(x => x.classification === k).length
  const usable = d.length - count('restricted')
  const parts = [
    `${usable} of ${d.length} documents are available to the agent for verifying claims about ${c.name}.`,
    count('confidential') ? `${count('confidential')} confidential — any counter-post quoting them needs compliance approval.` : '',
    count('restricted') ? `${count('restricted')} restricted — indexed, never shown to the agent.` : '',
    `Coverage: ${c.topics.slice(0, 3).join(', ').toLowerCase() || 'general claims'}.`,
  ]
  return parts.filter(Boolean).join(' ')
}

function CompanyCard({ c }: { c: Company }) {
  const { posts, uploadDocuments } = useStore()
  const [uploading, setUploading] = useState(false)
  const [docs, setDocs] = useState<PendingDoc[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const close = () => { setUploading(false); setDocs([]); setError('') }

  async function upload() {
    setBusy(true)
    setError('')
    try {
      await uploadDocuments(c.id, docs)
      close()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const mine = posts.filter(p => p.companyId === c.id)
  const openHigh = mine.filter(p => p.severity === 'high' && p.status === 'new').length

  const usable = c.documents.filter(d => d.classification !== 'restricted').length
  const metrics = [
    { label: 'Mentions', value: mine.length, to: `/app/feed?company=${c.id}&status=all` },
    { label: 'Open high priority', value: openHigh, to: `/app/feed?company=${c.id}&severity=high`, danger: openHigh > 0 },
    { label: 'Documents', value: c.documents.length },
    { label: 'Usable by agent', value: usable },
  ]
  const profile = [
    { label: 'Also known as', value: c.aliases.length > 0 && <div className="flex flex-wrap gap-1.5">{c.aliases.map(a => <Badge key={a}>{a}</Badge>)}</div> },
    { label: 'Key people', value: c.people.length > 0 && <span className="text-fg-2">{c.people.join(', ')}</span> },
    { label: 'Risk topics', value: c.topics.length > 0 && <div className="flex flex-wrap gap-1.5">{c.topics.map(t => <Badge key={t} tone="ready">{t}</Badge>)}</div> },
  ].filter(x => x.value)

  return (
    <article className="overflow-hidden rounded-panel border border-line bg-surface">
      <header className="flex flex-wrap items-center gap-3 p-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-control bg-selected font-semibold text-accent">{c.name[0]}</div>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-base font-semibold">{c.name}</h2>
          <p className="flex flex-wrap items-center gap-x-3 text-xs text-fg-3">
            <span>{c.sector}, {c.country}</span>
            {c.website && <a href={c.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline"><Globe size={14} />{c.website.replace(/^https?:\/\//, '').replace(/\/+$/, '')}</a>}
          </p>
        </div>
        <Badge tone="success">Monitoring</Badge>
      </header>

      <dl className="grid grid-cols-2 divide-line border-y border-line sm:grid-cols-4 sm:divide-x">
        {metrics.map(m => (
          <div key={m.label} className="px-4 py-3">
            <dt className="text-xs text-fg-3">{m.label}</dt>
            <dd className={cx('mt-1 text-2xl font-semibold', m.danger && 'text-danger')}>
              {m.to ? <Link to={m.to} className="hover:text-accent">{m.value}</Link> : m.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="grid lg:grid-cols-2 lg:divide-x lg:divide-line">
        <section className="p-4">
          <h3 className="text-sm font-semibold">Profile</h3>
          <p className="mb-2 text-xs text-fg-3">What the monitor matches mentions against</p>
          <ul className="divide-y divide-line">
            {profile.map(x => (
              <li key={x.label} className="grid grid-cols-[110px_1fr] items-start gap-3 py-2.5 text-sm">
                <span className="pt-0.5 text-xs text-fg-3">{x.label}</span>
                {x.value}
              </li>
            ))}
          </ul>
        </section>

        <section className="border-t border-line p-4 lg:border-t-0">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold">Documents</h3>
              <p className="text-xs text-fg-3">Evidence the agent checks claims against</p>
            </div>
            <Button className="h-8" onClick={() => setUploading(true)}><UploadSimple size={16} />Add</Button>
          </div>
          <p className="mt-3 flex gap-2 rounded-control bg-subtle px-3 py-2 text-sm text-fg-2">
            <Sparkle size={16} className="mt-0.5 shrink-0 text-accent" />{summarize(c)}
          </p>
          {c.documents.length > 0 && (
            <ul className="mt-2 divide-y divide-line">
              {c.documents.map(d => (
                <li key={d.id} className="py-2.5 text-sm">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="shrink-0 text-fg-3" />
                    <span className="min-w-0 flex-1 truncate">{d.name}</span>
                    {d.status === 'processing' && <Badge>Summarizing…</Badge>}
                    <ClassBadge c={d.classification} />
                  </div>
                  {d.summary ? (
                    <p className="mt-1 ml-6 text-xs leading-5 text-fg-2">{d.summary}</p>
                  ) : d.status === 'ready' && d.classification === 'restricted' ? (
                    <p className="mt-1 ml-6 text-xs text-fg-3">Summary visible to compliance only</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <Dialog open={uploading} onClose={close} title={`Add documents to ${c.name}`}>
        <DocsUpload docs={docs} onChange={setDocs} />
        {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" disabled={busy} onClick={close}>Cancel</Button>
          <Button variant="primary" disabled={!docs.length || busy} onClick={upload}>
            {busy ? 'Uploading…' : `Upload ${docs.length || ''}`}
          </Button>
        </div>
      </Dialog>
    </article>
  )
}

export default function Companies() {
  const { companies, addCompany } = useStore()
  const [adding, setAdding] = useState(false)
  return (
    <div className="space-y-4">
      <PageActions>
        <Button variant="primary" onClick={() => setAdding(true)}><Plus size={16} />Track another company</Button>
      </PageActions>
      {companies.map(c => <CompanyCard key={c.id} c={c} />)}
      <Dialog wide open={adding} onClose={() => setAdding(false)} title="Track another company">
        <CompanyWizard onDone={async (c, docs) => { await addCompany(c, docs); setAdding(false) }} />
      </Dialog>
    </div>
  )
}
