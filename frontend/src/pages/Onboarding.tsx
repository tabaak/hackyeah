import { ShieldCheck } from '@phosphor-icons/react'
import { useNavigate } from 'react-router-dom'
import { CompanyWizard } from '../components/CompanySetup'
import { useStore } from '../lib/store'
import { PRODUCT_NAME } from './Login'

export default function Onboarding() {
  const { addCompany } = useStore()
  const nav = useNavigate()
  return (
    <main className="min-h-dvh bg-canvas px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex items-center gap-2 text-fg-2">
          <ShieldCheck size={22} weight="duotone" className="text-accent" />
          <span className="font-medium">{PRODUCT_NAME}</span>
        </div>
        <h1 className="text-2xl font-semibold">Which company should we protect?</h1>
        <p className="mt-1 mb-8 text-fg-2">We use this to find mentions and tell real criticism apart from attacks. Takes about a minute.</p>
        <section className="rounded-panel border border-line bg-surface p-6">
          <CompanyWizard onDone={c => { addCompany(c); nav('/app/feed', { replace: true }) }} />
        </section>
      </div>
    </main>
  )
}
