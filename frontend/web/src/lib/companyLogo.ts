import { api } from './api'

export function companyLogoError(file: File): string | null {
  return !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024
    ? 'Choose a PNG, JPG or WebP image smaller than 2 MB.'
    : null
}

export async function uploadCompanyLogo(companyId: string, file: File, token: string): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const result = await api<{ logoUrl: string }>(`/companies/${companyId}/logo`, { method: 'PUT', body: form }, token)
  return result.logoUrl
}
