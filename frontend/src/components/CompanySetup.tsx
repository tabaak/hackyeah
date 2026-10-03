import { FileText, Trash } from '@phosphor-icons/react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { COUNTRIES, SECTORS, uid, type Classification, type CompanyDraft, type Doc } from '../lib/mock'
import { Button, cx, Field, inputCls } from '../lib/ui'
import { CompanyCreatedError } from '../lib/companyLogo'
import CompanyLogoPicker from './CompanyLogoPicker'

const split = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)

export type { CompanyDraft } from '../lib/mock'
// A file chosen in DocsUpload, not uploaded yet
export type PendingDoc = Pick<Doc, 'id' | 'name' | 'size' | 'classification'> & { file: File }

export function CompanyForm({ onSubmit, submitLabel, aside, initial, logo = null, onLogoChange }: { onSubmit: (c: CompanyDraft) => void; submitLabel: string; aside?: ReactNode; initial?: CompanyDraft; logo?: { file: File; preview: string } | null; onLogoChange?: (file: File | null) => void }) {
  const [sector, setSector] = useState(initial?.sector ?? 'Banking')
  const [topics, setTopics] = useState<string[]>(initial?.topics ?? SECTORS.Banking.slice(0, 3))

  function pickSector(s: string) {
    setSector(s)
    setTopics(SECTORS[s].slice(0, 3))
  }

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const name = String(f.get('name')).trim()
    onSubmit({
      name,
      website: String(f.get('website')).trim(),
      aliases: split(String(f.get('aliases'))),
      sector,
      country: String(f.get('country')),
      people: split(String(f.get('people'))),
      topics,
    })
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {onLogoChange && <CompanyLogoPicker file={logo?.file ?? null} preview={logo?.preview ?? null} onChange={onLogoChange} />}
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Company name">
          <input name="name" required autoFocus defaultValue={initial?.name} className={cx(inputCls, "w-full")} placeholder="Kestrel Bank" />
        </Field>
        <Field label="Website" optional hint="Helps tell your company apart from namesakes">
          <input name="website" type="url" defaultValue={initial?.website} className={cx(inputCls, "w-full")} placeholder="https://example.com" />
        </Field>
      </div>
      <Field label="Other names people use" optional hint="Short names, brands, ticker, app name — comma separated">
        <input name="aliases" defaultValue={initial?.aliases.join(', ')} className={cx(inputCls, "w-full")} placeholder="Short names, brands, ticker" />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Industry">
          <select value={sector} onChange={e => pickSector(e.target.value)} className={cx(inputCls, "w-full")}>
            {Object.keys(SECTORS).map(s => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Main market" hint="Sets languages and regional sources">
          <select name="country" defaultValue={initial?.country ?? 'Poland'} className={cx(inputCls, "w-full")}>
            {COUNTRIES.map(c => <option key={c}>{c}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Key people" optional hint="Executives often targeted by name — comma separated">
        <input name="people" defaultValue={initial?.people.join(', ')} className={cx(inputCls, "w-full")} placeholder="Key people, separated by commas" />
      </Field>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">Risk topics to watch</legend>
        <div className="flex flex-wrap gap-2">
          {SECTORS[sector].map(t => {
            const on = topics.includes(t)
            return (
              <label
                key={t}
                className={cx(
                  'cursor-pointer rounded-full border px-3 py-1.5 text-sm motion-control has-focus-visible:outline-2 has-focus-visible:outline-accent',
                  on ? 'border-accent bg-selected text-fg' : 'border-line text-fg-2 hover:border-control',
                )}
              >
                <input type="checkbox" className="sr-only" checked={on} onChange={() => setTopics(on ? topics.filter(x => x !== t) : [...topics, t])} />
                {t}
              </label>
            )
          })}
        </div>
      </fieldset>
      <div className="flex items-center gap-3 pt-2">
        {aside}
        <Button variant="primary" type="submit" className="ml-auto">{submitLabel}</Button>
      </div>
    </form>
  )
}

const MAX_FILES = 8
const MAX_BYTES = 5 * 1024 * 1024
const CLASSES: Classification[] = ['public', 'internal', 'confidential', 'restricted']

export function DocsUpload({ docs, onChange }: { docs: PendingDoc[]; onChange: (d: PendingDoc[]) => void }) {
  const [error, setError] = useState('')
  const [drag, setDrag] = useState(false)

  function add(files: FileList | null) {
    if (!files) return
    const list = [...files]
    const tooBig = list.filter(f => f.size > MAX_BYTES)
    const ok = list.filter(f => f.size <= MAX_BYTES).slice(0, MAX_FILES - docs.length)
    setError(tooBig.length ? `${tooBig.map(f => f.name).join(', ')}: larger than 5 MB` : list.length > ok.length ? `Up to ${MAX_FILES} documents` : '')
    onChange([...docs, ...ok.map(f => ({ id: uid(), name: f.name, size: f.size, classification: 'internal' as const, file: f }))])
  }

  return (
    <div className="space-y-4">
      <label
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files) }}
        className={cx(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-panel border-2 border-dashed px-6 py-10 text-center motion-control has-focus-visible:outline-2 has-focus-visible:outline-accent',
          drag ? 'border-accent bg-selected' : 'border-line hover:border-control',
        )}
      >
        <span className="font-medium">Drop files or click to choose</span>
        <span className="text-xs text-fg-3">PDF with a text layer or TXT up to {MAX_FILES} files, 5 MB each</span>
        <input type="file" multiple accept=".pdf,.txt" className="sr-only" onChange={e => { add(e.target.files); e.target.value = '' }} />
      </label>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {docs.length > 0 && (
        <ul className="divide-y divide-line rounded-panel border border-line">
          {docs.map(d => (
            <li key={d.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
              <FileText size={18} className="shrink-0 text-fg-3" />
              <span className="min-w-0 flex-1 truncate text-sm">{d.name}</span>
              <span className="font-mono text-xs text-fg-3">{(d.size / 1024).toFixed(0)} KB</span>
              <select
                aria-label={`Classification of ${d.name}`}
                value={d.classification}
                onChange={e => onChange(docs.map(x => (x.id === d.id ? { ...x, classification: e.target.value as Classification } : x)))}
                className={cx(inputCls, 'h-8 w-36')}
              >
                {CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <Button variant="ghost" className="h-8 w-8 px-0" aria-label={`Remove ${d.name}`} onClick={() => onChange(docs.filter(x => x.id !== d.id))}>
                <Trash size={16} />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs leading-5 text-fg-3">
        Classification controls what the agent may quote publicly. <b className="font-medium text-fg-2">Confidential</b> facts need compliance approval;{' '}
        <b className="font-medium text-fg-2">restricted</b> files are indexed but never shown to the agent.
      </p>
    </div>
  )
}

// Two steps: profile → optional documents. Shared by onboarding and "Track another company".
// `aside` renders next to Continue on the first step (e.g. sign out during onboarding).
export function CompanyWizard({ onDone, onExit, aside, initialCompany }: { onDone: (c: CompanyDraft, docs: PendingDoc[], logo: File | null) => Promise<void>; onExit: () => void; aside?: ReactNode; initialCompany?: CompanyDraft }) {
  const [draft, setDraft] = useState<CompanyDraft | null>(null)
  const [profileStep, setProfileStep] = useState(true)
  const [logo, setLogo] = useState<{ file: File; preview: string } | null>(null)
  const [docs, setDocs] = useState<PendingDoc[]>([])
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => () => { if (logo) URL.revokeObjectURL(logo.preview) }, [logo])

  function chooseLogo(file: File | null) {
    setLogo(file ? { file, preview: URL.createObjectURL(file) } : null)
  }

  async function finish(d: PendingDoc[]) {
    if (!draft || busy || created) return
    setBusy(true)
    setError('')
    try {
      await onDone(draft, d, logo?.file ?? null)
    } catch (e) {
      if (e instanceof CompanyCreatedError) setCreated(true)
      setError(e instanceof Error && !(e instanceof TypeError) ? e.message : 'The company could not be saved. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <ol className="mb-6 flex items-center gap-3 text-sm" aria-label="Setup progress">
        {['Company', 'Documents'].map((s, i) => {
          const active = (profileStep ? 0 : 1) === i
          const done = i === 0 && !profileStep
          return (
            <li key={s} className="flex items-center gap-2" aria-current={active ? 'step' : undefined}>
              {i > 0 && <span className="h-px w-8 bg-line" />}
              <span className={cx('motion-control flex h-6 w-6 items-center justify-center rounded-full font-mono text-xs', active || done ? 'bg-accent text-on-accent' : 'bg-subtle text-fg-3')}>{i + 1}</span>
              <span className={cx('motion-control', active ? 'font-medium text-fg' : 'text-fg-3')}>{s}{i === 1 && ' · optional'}</span>
            </li>
          )
        })}
      </ol>
      {profileStep || !draft ? (
        <CompanyForm submitLabel="Continue" onSubmit={c => { setDraft(c); setProfileStep(false) }} aside={aside} initial={draft ?? initialCompany} logo={logo} onLogoChange={chooseLogo} />
      ) : created ? (
        <div className="space-y-5">
          <p className="font-medium">{draft.name} was added</p>
          <p role="alert" className="text-sm text-danger">{error}</p>
          <div className="flex justify-end"><Button variant="primary" onClick={onExit}>Done</Button></div>
        </div>
      ) : (
        <fieldset disabled={busy} aria-busy={busy} className="motion-page min-w-0 space-y-5">
          <p className="text-[15px] leading-6 text-fg-2">
            Upload documents the agent can use to check claims about <b className="text-fg">{draft.name}</b> — press releases, status reports, ops logs, FAQs. You can skip this and add them later.
          </p>
          <DocsUpload docs={docs} onChange={setDocs} />
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          {busy && <p role="status" className="text-sm text-fg-2">Saving company…</p>}
          <div className="flex justify-between gap-3 pt-2">
            <Button variant="ghost" disabled={busy} onClick={() => { setError(''); setProfileStep(true) }}>Back</Button>
            <div className="flex gap-3">
              <Button variant="secondary" disabled={busy} onClick={() => finish([])}>Skip for now</Button>
              <Button variant="primary" disabled={!docs.length || busy} onClick={() => finish(docs)}>{busy ? 'Uploading…' : 'Start monitoring'}</Button>
            </div>
          </div>
        </fieldset>
      )}
    </div>
  )
}
