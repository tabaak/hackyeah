import { PencilSimple } from '@phosphor-icons/react'
import { useRef, useState } from 'react'
import type { Company } from '../lib/mock'
import { companyLogoError } from '../lib/companyLogo'
import { useStore } from '../lib/store'
import { Button, Dialog } from '../lib/ui'

export default function CompanyLogo({ company }: { company: Company }) {
  const { setCompanyLogo } = useStore()
  const input = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const url = company.logoUrl && company.logoUrl !== failedUrl ? company.logoUrl : null
  const initial = company.name[0]?.toUpperCase()

  async function save(file: File | null) {
    const validationError = file && companyLogoError(file)
    if (validationError) {
      setError(validationError)
      return
    }
    setBusy(true)
    setError('')
    try {
      await setCompanyLogo(company.id, file)
      setOpen(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The logo could not be saved. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label={`${company.logoUrl ? 'Change' : 'Add'} logo for ${company.name}`}
        title={company.logoUrl ? 'Change company logo' : 'Add company logo'}
        onClick={() => { setError(''); setOpen(true) }}
        className="motion-control group relative flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-control bg-selected font-semibold text-accent outline-offset-4 hover:ring-1 hover:ring-accent focus-visible:outline-2 focus-visible:outline-accent"
      >
        {url ? <img src={url} alt="" onError={() => setFailedUrl(url)} className="size-full min-h-0 min-w-0 object-cover" /> : initial}
        <span className="motion-control absolute inset-0 grid place-items-center bg-canvas/80 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"><PencilSimple size={16} /></span>
      </button>
      <Dialog open={open} onClose={() => { if (!busy) setOpen(false) }} title="Company logo">
        <div className="flex items-center gap-4">
          <div className="flex size-20 shrink-0 items-center justify-center overflow-hidden rounded-panel border border-line bg-selected text-2xl font-semibold text-accent">
            {url ? <img src={url} alt={`${company.name} logo`} className="size-full min-h-0 min-w-0 object-cover" /> : initial}
          </div>
          <div><p className="font-medium">{company.name}</p><p className="mt-1 text-sm text-fg-3">PNG, JPG or WebP up to 2 MB</p></div>
        </div>
        <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" disabled={busy} onChange={e => {
          const file = e.currentTarget.files?.[0]
          e.currentTarget.value = ''
          if (file) void save(file)
        }} />
        {error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}
        {busy && <p role="status" className="mt-4 text-sm text-fg-2">Saving logo…</p>}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          {company.logoUrl && <Button variant="ghost" disabled={busy} onClick={() => void save(null)}>Remove logo</Button>}
          <Button variant="primary" disabled={busy} onClick={() => input.current?.click()}>Choose image</Button>
        </div>
      </Dialog>
    </>
  )
}
