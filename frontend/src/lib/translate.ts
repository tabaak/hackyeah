import { useEffect, useRef, useState } from 'react'

// Google Translate's public "gtx" endpoint: free, no key, CORS-enabled. It is unofficial (no SLA), so callers
// must handle failure; googleTranslateUrl is the manual fallback.
const ENDPOINT = 'https://translate.googleapis.com/translate_a/single'
const CHUNK_CHARS = 1500 // the endpoint takes the text in the URL: keep requests short

export interface Translation { text: string; from: string } // `from` = detected ISO language code

const cache = new Map<string, Translation>()
export const languageName = (code: string) => {
  try { return new Intl.DisplayNames(['en'], { type: 'language' }).of(code) ?? code } catch { return code }
}

export function googleTranslateUrl(text: string) {
  return `https://translate.google.com/?sl=auto&tl=en&op=translate&text=${encodeURIComponent(text.slice(0, 4000))}`
}

// Split on paragraph, then sentence, then hard-cut boundaries so no chunk is over CHUNK_CHARS.
function chunk(text: string, max = CHUNK_CHARS): string[] {
  const out: string[] = []
  let cur = ''
  const push = (piece: string) => {
    if (cur && cur.length + piece.length > max) { out.push(cur); cur = '' }
    cur += piece
  }
  for (const para of text.split(/(?<=\n)/)) {
    if (para.length <= max) { push(para); continue }
    for (const sentence of para.split(/(?<=[.!?…。])\s+/)) {
      if (sentence.length <= max) { push(sentence + ' '); continue }
      for (let i = 0; i < sentence.length; i += max) push(sentence.slice(i, i + max))
    }
  }
  if (cur) out.push(cur)
  return out.filter(c => c.trim())
}

async function translateChunk(q: string, signal?: AbortSignal): Promise<Translation> {
  const res = await fetch(`${ENDPOINT}?${new URLSearchParams({ client: 'gtx', sl: 'auto', tl: 'en', dt: 't', q })}`, { signal })
  if (!res.ok) throw new Error(`Translation failed (${res.status})`)
  const data = (await res.json()) as [[string, string][], unknown, string]
  return { text: data[0].map(s => s[0]).join(''), from: data[2] ?? 'und' }
}

export async function translate(text: string, signal?: AbortSignal): Promise<Translation> {
  const hit = cache.get(text)
  if (hit) return hit
  const parts = await Promise.all(chunk(text).map(c => translateChunk(c, signal)))
  const result = { text: parts.map(p => p.text).join('').trim(), from: parts[0]?.from ?? 'und' }
  cache.set(text, result)
  return result
}

export type TranslationState = {
  status: 'idle' | 'loading' | 'done' | 'error'
  result: Translation | null
  showing: boolean // translated text is the one displayed
  run: () => void // translate, or flip between original and translation once translated
}

export function useTranslation(text: string): TranslationState {
  const [status, setStatus] = useState<TranslationState['status']>('idle')
  const [result, setResult] = useState<Translation | null>(null)
  const [showing, setShowing] = useState(false)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const run = () => {
    if (status === 'loading') return
    if (result) { setShowing(s => !s); return }
    controller.current?.abort()
    controller.current = new AbortController()
    setStatus('loading')
    translate(text, controller.current.signal).then(r => {
      setResult(r); setShowing(r.from !== 'en'); setStatus('done')
    }, (e: Error) => { if (e.name !== 'AbortError') setStatus('error') })
  }
  return { status, result, showing, run }
}
