// Shared types and static reference data. Live data (companies, mentions, notifications, analytics) comes from the API.

export type Severity = 'high' | 'medium' | 'low'
export type Classification = 'public' | 'internal' | 'confidential' | 'restricted'
export type Platform = 'x' | 'facebook' | 'threads' | 'news'
export type Verdict = 'contradicted_by_documents' | 'supported_by_documents' | 'insufficient_evidence' | 'opinion'
export type PostStatus = 'new' | 'responded' | 'dismissed'

export interface Doc {
  id: string
  name: string
  size: number
  classification: Classification
  status: 'processing' | 'ready' | 'failed'
  summary?: string | null // AI summary; null while processing, and for restricted unless compliance
}

export interface Company {
  id: string
  name: string
  website: string
  aliases: string[]
  sector: string
  country: string
  people: string[]
  topics: string[]
  documents: Doc[]
  createdAt: number
}

export type CompanyDraft = Omit<Company, 'id' | 'documents' | 'createdAt'>

export const DEMO_COMPANY_PROFILE: CompanyDraft = {
  name: 'Goldman Sachs',
  website: 'https://www.goldmansachs.com',
  aliases: ['Goldman', 'GS'],
  sector: 'Banking',
  country: 'United States',
  people: [],
  topics: ['Regulatory action', 'Trading losses', 'Data breach'],
}

export interface Post {
  id: string
  companyId: string
  platform: Platform
  author: string
  handle: string
  text: string
  at: number
  severity: Severity
  verdict: Verdict
  reason: string
  reach: number
  cluster: { size: number; accounts: number } | null
  injection: boolean
  status: PostStatus
  url?: string | null // link to the original post or article
}

export const SECTORS: Record<string, string[]> = {
  Banking: ['Liquidity / bank run', 'Frozen withdrawals', 'App or card outage', 'Data breach', 'Regulatory action', 'Fraud & scams', 'Trading losses', 'Market manipulation', 'Sanctions', 'Layoffs'],
  Defence: ['Delivery delays', 'Export control', 'Product failure', 'Sanctions', 'Leadership', 'Data breach'],
  Fintech: ['Frozen accounts', 'App outage', 'Data breach', 'Licence / regulator', 'Fraud & scams'],
  Energy: ['Supply disruption', 'Safety incident', 'Pricing', 'Environmental', 'Regulatory action'],
  Other: ['Product quality', 'Data breach', 'Leadership', 'Legal action', 'Layoffs'],
}

export const COUNTRIES = ['Poland', 'Germany', 'Ukraine', 'Lithuania', 'Czechia', 'United Kingdom', 'United States', 'Global']

export const PLATFORM_LABEL: Record<Platform, string> = {
  x: 'X', facebook: 'Facebook', threads: 'Threads', news: 'News',
}

// The post's own link when the API has one; otherwise a profile URL derived from the handle
export function sourceUrl(p: Pick<Post, 'platform' | 'handle' | 'url'>) {
  if (p.url) return p.url
  const h = p.handle.replace(/^@/, '')
  if (p.platform === 'x') return `https://x.com/${h}`
  if (p.platform === 'threads') return `https://www.threads.net/@${h}`
  return `https://${h}`
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  contradicted_by_documents: 'Contradicted by documents',
  supported_by_documents: 'Supported by documents',
  insufficient_evidence: 'Insufficient evidence',
  opinion: 'Opinion / assessment',
}

export const uid = () => Math.random().toString(36).slice(2, 10)

export type Range = '24h' | '7d' | '30d'
export const RANGES: Record<Range, { label: string; ms: number }> = {
  '24h': { label: '24 hours', ms: 864e5 },
  '7d': { label: '7 days', ms: 7 * 864e5 },
  '30d': { label: '30 days', ms: 30 * 864e5 },
}

// Social posts for the login reels — static, illustrative
export const REEL_POSTS: { platform: Platform; handle: string; text: string; threat?: boolean }[] = [
  { platform: 'x', handle: '@mkt_insider', text: 'BREAKING: bank froze all withdrawals. Get your money out now!', threat: true },
  { platform: 'threads', handle: '@personalfinance', text: 'Their app works fine for me, transfer went through in seconds.' },
  { platform: 'threads', handle: '@insider_news', text: 'Sources: regulator raid tomorrow morning. Share before deleted.', threat: true },
  { platform: 'facebook', handle: 'Anna K.', text: 'Proud of our team shipping the new payments platform today.' },
  { platform: 'facebook', handle: 'moneytok', text: 'POV: the ATM says NO 😱 #bankrun', threat: true },
  { platform: 'news', handle: 'Daily Ledger', text: 'Quarterly results beat expectations as deposits grow 4%.' },
  { platform: 'facebook', handle: 'Savers Group', text: 'Anyone know if branches are open on Saturday?' },
  { platform: 'x', handle: '@defence_watch', text: 'Supplier halted ALL June deliveries — army left without ammo.', threat: true },
  { platform: 'threads', handle: '@europe_daily', text: 'Good thread on how disinformation campaigns get amplified.' },
  { platform: 'x', handle: '@leaks_eu', text: 'Customer database of 2M accounts for sale. Proof inside.', threat: true },
  { platform: 'news', handle: 'EuroWire', text: 'Bank confirms brief ATM maintenance in one region.' },
  { platform: 'facebook', handle: 'Piotr N.', text: 'Hiring: risk analysts for our Warsaw office.' },
]
