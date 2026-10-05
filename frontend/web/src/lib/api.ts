import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY, {
  global: {
    fetch: (input, init) => fetch(input, {
      ...init,
      signal: init?.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000),
    }),
  },
})

// Vite proxies local API requests, including when the page is viewed on a different port.
const API_URL = import.meta.env.DEV ? '/api/v1' : import.meta.env.VITE_API_URL ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const timeout = AbortSignal.timeout(15_000)
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout
  try {
    signal.throwIfAborted()
    // The auth callback already supplies a current token; do not wait for a second session refresh.
    if (!token) {
      const { data, error } = await Promise.race([
        supabase.auth.getSession(),
        new Promise<never>((_, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true })),
      ])
      if (error) throw error
      token = data.session?.access_token
    }
    if (!token) throw new ApiError(401, 'Please sign in again.')
    signal.throwIfAborted()
    const headers = new Headers(init.headers)
    headers.set('Authorization', `Bearer ${token}`)
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const res = await fetch(`${API_URL}${path}`, { ...init, headers, signal })
    if (!res.ok) {
      const { detail } = await res.json().catch(() => ({}))
      const message = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map(e => e.msg).join('; ')
        : res.statusText
      throw new ApiError(res.status, message || 'Request failed')
    }
    return res.status === 204 ? (undefined as T) : await res.json()
  } catch (error) {
    if (init.signal?.aborted) throw error
    if (timeout.aborted) throw new Error('The server took too long to respond. Please try again.')
    if (error instanceof TypeError) throw new Error('The server could not be reached. Please try again.')
    throw error
  }
}
