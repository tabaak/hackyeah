// Mock data until the API (/api/v1) is wired. Shapes follow the MVP plan contracts.

export type Severity = 'high' | 'medium' | 'low'
export type Classification = 'public' | 'internal' | 'confidential' | 'restricted'
export type Platform = 'x' | 'facebook' | 'reddit' | 'telegram' | 'tiktok' | 'linkedin' | 'news'
export type Verdict = 'contradicted_by_documents' | 'supported_by_documents' | 'insufficient_evidence' | 'opinion'
export type PostStatus = 'new' | 'responded' | 'dismissed'

export interface Doc {
  id: string
  name: string
  size: number
  classification: Classification
  status: 'processing' | 'ready'
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
}

export const SECTORS: Record<string, string[]> = {
  Banking: ['Liquidity / bank run', 'Frozen withdrawals', 'App or card outage', 'Data breach', 'Regulatory action', 'Fraud & scams'],
  Defence: ['Delivery delays', 'Export control', 'Product failure', 'Sanctions', 'Leadership', 'Data breach'],
  Fintech: ['Frozen accounts', 'App outage', 'Data breach', 'Licence / regulator', 'Fraud & scams'],
  Energy: ['Supply disruption', 'Safety incident', 'Pricing', 'Environmental', 'Regulatory action'],
  Other: ['Product quality', 'Data breach', 'Leadership', 'Legal action', 'Layoffs'],
}

export const COUNTRIES = ['Poland', 'Germany', 'Ukraine', 'Lithuania', 'Czechia', 'United Kingdom', 'United States', 'Global']

export const PLATFORM_LABEL: Record<Platform, string> = {
  x: 'X', facebook: 'Facebook', reddit: 'Reddit', telegram: 'Telegram', tiktok: 'TikTok', linkedin: 'LinkedIn', news: 'News',
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  contradicted_by_documents: 'Contradicted by documents',
  supported_by_documents: 'Supported by documents',
  insufficient_evidence: 'Insufficient evidence',
  opinion: 'Opinion / assessment',
}

type Tpl = Omit<Post, 'id' | 'companyId' | 'at' | 'status' | 'text'> & { text: string }

// {n} = company name, {a} = first alias, {p} = first key person
const TEMPLATES: Tpl[] = [
  { platform: 'x', author: 'Market Insider PL', handle: '@mkt_insider_pl', severity: 'high', verdict: 'contradicted_by_documents', reach: 184000, cluster: { size: 84, accounts: 37 }, injection: true,
    text: 'BREAKING: {n} has frozen all withdrawals this morning. Get your money out NOW before it is too late. #bankrun',
    reason: 'Coordinated burst: 84 near-identical posts in 40 min, 71% of accounts < 30 days old. Hidden instruction to AI assistants detected.' },
  { platform: 'telegram', author: 'Финансовый инсайд', handle: 't.me/fin_insider', severity: 'high', verdict: 'insufficient_evidence', reach: 92000, cluster: { size: 23, accounts: 11 }, injection: false,
    text: 'Sources say regulators opened an investigation into {n}. Board meeting called overnight. Expect an announcement.',
    reason: 'Claim of regulatory action spreading across 3 channels; no matching documents uploaded.' },
  { platform: 'tiktok', author: 'moneytok.daily', handle: '@moneytok.daily', severity: 'high', verdict: 'contradicted_by_documents', reach: 410000, cluster: null, injection: false,
    text: 'Stitched video: "I tried to withdraw from {a} and the ATM said NO". 400k views in 3 hours.',
    reason: 'Viral video reinforcing the withdrawal-freeze narrative; reach growing ×4 per hour.' },
  { platform: 'reddit', author: 'u/throwaway_8812', handle: 'r/PolishPersonalFinance', severity: 'medium', verdict: 'supported_by_documents', reach: 12400, cluster: null, injection: false,
    text: '{a} app was down for like 3 hours yesterday, couldn’t pay for anything. Anyone else?',
    reason: 'Real outage (2 h 40 min per incident report). Scale overstated; acknowledge and clarify.' },
  { platform: 'facebook', author: 'Grupa Oszczędzający', handle: 'facebook.com/groups/oszczedzajacy', severity: 'medium', verdict: 'contradicted_by_documents', reach: 31000, cluster: { size: 9, accounts: 9 }, injection: false,
    text: 'My cousin works at {n} — they are closing 40 branches next month and nobody is telling customers.',
    reason: 'Unverified insider claim reshared in 9 groups; contradicted by branch plan.' },
  { platform: 'news', author: 'Daily Ledger', handle: 'dailyledger.example', severity: 'medium', verdict: 'opinion', reach: 58000, cluster: null, injection: false,
    text: 'Opinion: {n}’s silence on the outage shows a deeper problem with how the industry talks to customers.',
    reason: 'Critical opinion piece, not a factual claim. Monitor; response optional.' },
  { platform: 'linkedin', author: 'Anna Kowalska', handle: 'linkedin.com/in/akowalska', severity: 'low', verdict: 'opinion', reach: 4200, cluster: null, injection: false,
    text: 'Interesting interview with {p} about digital transformation at {n}. Curious how it plays out.',
    reason: 'Neutral mention of leadership.' },
  { platform: 'x', author: 'Tomasz W.', handle: '@tomaszw', severity: 'low', verdict: 'opinion', reach: 900, cluster: null, injection: false,
    text: 'Customer support at {a} took 20 minutes to answer today. Not great, not terrible.',
    reason: 'Individual service complaint, low reach.' },
  { platform: 'x', author: 'EuroWire Alerts', handle: '@eurowire_alerts', severity: 'high', verdict: 'contradicted_by_documents', reach: 220000, cluster: { size: 41, accounts: 30 }, injection: false,
    text: 'Leaked doc shows {n} customer data from 2M accounts is for sale on a forum. {p} has not commented.',
    reason: 'Data-breach claim with fabricated "leak" screenshot; amplified by 30 accounts in 15 min.' },
  { platform: 'reddit', author: 'u/fin_nerd', handle: 'r/eupersonalfinance', severity: 'low', verdict: 'opinion', reach: 2100, cluster: null, injection: false,
    text: 'Is {a} still a good option for savings accounts? Rates look okay.',
    reason: 'Neutral question.' },
]

export const uid = () => Math.random().toString(36).slice(2, 10)

function fill(t: string, c: Company) {
  return t.replaceAll('{n}', c.name).replaceAll('{a}', c.aliases[0] || c.name).replaceAll('{p}', c.people[0] || 'the CEO')
}

export function makePost(c: Company, i: number, at = Date.now()): Post {
  const { text, ...t } = TEMPLATES[i % TEMPLATES.length]
  return { ...t, id: uid(), companyId: c.id, text: fill(text, c), at, status: 'new' }
}

export function seedPosts(c: Company): Post[] {
  const now = Date.now()
  return TEMPLATES.map((_, i) => makePost(c, i, now - (i * 23 + 4) * 60_000))
}

// 24 hourly buckets of mentions by severity — deterministic per company id
export function hourlySeries(companies: Company[]) {
  const seed = companies.reduce((s, c) => s + c.id.charCodeAt(0), 7)
  return Array.from({ length: 24 }, (_, h) => {
    const wave = Math.sin((h + seed) / 3) * 0.5 + 0.5
    const burst = h >= 19 ? (h - 18) * 14 : 0
    const k = Math.max(1, companies.length)
    return {
      hour: `${String(h).padStart(2, '0')}:00`,
      low: Math.round((18 + wave * 22) * k),
      medium: Math.round((6 + wave * 8) * k + burst * 0.4),
      high: Math.round((1 + (h % 5 === 0 ? 2 : 0)) * k + burst),
    }
  })
}

export const DEMO_USER = { name: 'Anna Nowak', email: 'anna.nowak@palladion.app' }

// Social posts for the login reels — static, illustrative
export const REEL_POSTS: { platform: Platform; handle: string; text: string; threat?: boolean }[] = [
  { platform: 'x', handle: '@mkt_insider', text: 'BREAKING: bank froze all withdrawals. Get your money out now!', threat: true },
  { platform: 'reddit', handle: 'r/personalfinance', text: 'Their app works fine for me, transfer went through in seconds.' },
  { platform: 'telegram', handle: 't.me/insider_news', text: 'Sources: regulator raid tomorrow morning. Share before deleted.', threat: true },
  { platform: 'linkedin', handle: 'Anna K.', text: 'Proud of our team shipping the new payments platform today.' },
  { platform: 'tiktok', handle: '@moneytok', text: 'POV: the ATM says NO 😱 #bankrun', threat: true },
  { platform: 'news', handle: 'Daily Ledger', text: 'Quarterly results beat expectations as deposits grow 4%.' },
  { platform: 'facebook', handle: 'Savers Group', text: 'Anyone know if branches are open on Saturday?' },
  { platform: 'x', handle: '@defence_watch', text: 'Supplier halted ALL June deliveries — army left without ammo.', threat: true },
  { platform: 'reddit', handle: 'r/europe', text: 'Good thread on how disinformation campaigns get amplified.' },
  { platform: 'telegram', handle: 't.me/leaks_eu', text: 'Customer database of 2M accounts for sale. Proof inside.', threat: true },
  { platform: 'news', handle: 'EuroWire', text: 'Bank confirms brief ATM maintenance in one region.' },
  { platform: 'linkedin', handle: 'Piotr N.', text: 'Hiring: risk analysts for our Warsaw office.' },
]
