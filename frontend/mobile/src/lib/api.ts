import { supabase } from './supabase'

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'
const TIMEOUT_MS = 15_000

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// Same contract as frontend/web/src/lib/api.ts: Supabase access token as the bearer
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession()
  // A backend that accepts the connection but never answers would otherwise spin forever
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    signal: controller.signal,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${data.session?.access_token}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
  }).catch((e: unknown) => {
    throw controller.signal.aborted ? new Error('The server is not responding') : e
  }).finally(() => clearTimeout(timer))
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({}))
    throw new ApiError(res.status, typeof detail === 'string' ? detail : res.statusText || 'Request failed')
  }
  return res.status === 204 ? (undefined as T) : res.json()
}
