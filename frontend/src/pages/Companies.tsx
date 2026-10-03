import { FileText, Globe, Plus, Sparkle, UploadSimple } from '@phosphor-icons/react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CompanyWizard, DocsUpload } from '../components/CompanySetup'
import type { Classification, Company, Doc } from '../lib/mock'
import { useStore } from '../lib/store'
import { Badge, Button, ClassBadge, Dialog } from '../lib/ui'

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
  const { posts, updateCompany } = useStore()
  const [uploading, setUploading] = useState(false)
  const [docs, setDocs] = useState<Doc[]>([])
  const mine = posts.filter(p => p.companyId === c.id)
  const openHigh = mine.filter(p => p.severity === 'high' && p.status === 'new').length

  return (
    <article className="rounded-panel border border-line bg-surface">
      <header className="flex flex-wrap items-start gap-3 border-b border-line p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-panel bg-selected font-semibold text-accent">{c.name[0]}</div>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold">{c.name}</h2>
          <p className="flex flex-wrap items-center gap-x-2 text-sm text-fg-2">
            {c.sector} · {c.country}
            {c.website && <a href={c.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline"><Globe size={14} />{c.website.replace(/^https?:\/\//, '')}</a>}
          </p>
        </div>
        <Badge tone="success">Monitoring</Badge>
      </header>

      <div className="grid gap-6 p-4 lg:grid-cols-[1fr_1.3fr]">
        <div className="space-y-4 text-sm">
          <dl className="grid grid-cols-2 gap-3">
            <div><dt className="text-xs text-fg-3">Mentions</dt><dd className="text-xl font-semibold">{mine.length}</dd></div>
            <div>
              <dt className="text-xs text-fg-3">High priority · open</dt>
              <dd className="text-xl font-semibold">
                <Link to={`/app/feed?company=${c.id}&severity=high`} className={openHigh ? 'text-danger hover:underline' : ''}>{openHigh}</Link>
              </dd>
            </div>
          </dl>
          {c.aliases.length > 0 && (
            <div>
              <div className="mb-1 text-xs text-fg-3">Also known as</div>
              <div className="flex flex-wrap gap-1.5">{c.aliases.map(a => <Badge key={a}>{a}</Badge>)}</div>
            </div>
          )}
          {c.people.length > 0 && (
            <div><div className="mb-1 text-xs text-fg-3">Key people</div><p className="text-fg-2">{c.people.join(', ')}</p></div>
          )}
          <div>
            <div className="mb-1 text-xs text-fg-3">Risk topics</div>
            <div className="flex flex-wrap gap-1.5">{c.topics.map(t => <Badge key={t} tone="ready">{t}</Badge>)}</div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-panel bg-subtle p-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-fg-2"><Sparkle size={14} className="text-accent" />Document summary</div>
            <p className="text-sm leading-6 text-fg-2">{summarize(c)}</p>
          </div>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Documents <span className="font-mono font-normal text-fg-3">{c.documents.length}</span></h3>
            <Button className="h-8" onClick={() => setUploading(true)}><UploadSimple size={16} />Add</Button>
          </div>
          {c.documents.length > 0 && (
            <ul className="divide-y divide-line rounded-panel border border-line">
              {c.documents.map(d => (
                <li key={d.id} className="flex items-center gap-2 px-3 py-2 text-sm">
                  <FileText size={16} className="shrink-0 text-fg-3" />
                  <span className="min-w-0 flex-1 truncate">{d.name}</span>
                  <Badge tone="ready">Processed</Badge>
                  <ClassBadge c={d.classification} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <Dialog open={uploading} onClose={() => { setUploading(false); setDocs([]) }} title={`Add documents · ${c.name}`}>
        <DocsUpload docs={docs} onChange={setDocs} />
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => { setUploading(false); setDocs([]) }}>Cancel</Button>
          <Button
            variant="primary"
            disabled={!docs.length}
            onClick={() => {
              updateCompany({ ...c, documents: [...c.documents, ...docs.map(d => ({ ...d, status: 'ready' as const }))] })
              setUploading(false)
              setDocs([])
            }}
          >Upload {docs.length || ''}</Button>
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-fg-2">Companies we watch, the documents behind each counter-post, and what the agent can use.</p>
        <Button variant="primary" onClick={() => setAdding(true)}><Plus size={16} />Track another company</Button>
      </div>
      {companies.map(c => <CompanyCard key={c.id} c={c} />)}
      <Dialog wide open={adding} onClose={() => setAdding(false)} title="Track another company">
        <CompanyWizard onDone={c => { addCompany(c); setAdding(false) }} />
      </Dialog>
    </div>
  )
}
