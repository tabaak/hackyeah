import { ImageSquare } from '@phosphor-icons/react'
import { useRef, useState } from 'react'
import { companyLogoError } from '../lib/companyLogo'
import { Button } from '../lib/ui'

export default function CompanyLogoPicker({ file, preview, onChange }: { file: File | null; preview: string | null; onChange: (file: File | null) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')

  function choose(file: File) {
    const error = companyLogoError(file)
    setError(error ?? '')
    if (!error) onChange(file)
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Company logo <span className="font-normal text-fg-3">· optional</span></p>
      <div className="flex items-center gap-4">
        <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-panel border border-line bg-selected text-accent">
          {preview ? <img src={preview} alt="Company logo preview" className="size-full min-h-0 min-w-0 object-cover" onError={() => { setError('This image could not be opened. Choose another PNG, JPG or WebP.'); onChange(null) }} /> : <ImageSquare size={24} />}
        </div>
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => input.current?.click()}>{file ? 'Change image' : 'Choose image'}</Button>
            {file && <Button type="button" variant="ghost" aria-label="Remove selected logo" onClick={() => { onChange(null); setError('') }}>Remove</Button>}
          </div>
          <p className="text-xs text-fg-3">PNG, JPG or WebP up to 2 MB</p>
          {file && <p className="truncate text-xs text-fg-2" title={file.name}>{file.name}</p>}
        </div>
      </div>
      <input ref={input} aria-label="Choose company logo" type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={e => {
        const file = e.currentTarget.files?.[0]
        e.currentTarget.value = ''
        if (file) choose(file)
      }} />
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    </div>
  )
}
