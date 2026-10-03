import { SignOut } from '@phosphor-icons/react'
import { useNavigate } from 'react-router-dom'
import { CompanyWizard } from '../components/CompanySetup'
import { useStore } from '../lib/store'
import { Button } from '../lib/ui'
import { LogoMark, PRODUCT_NAME } from './Login'

export default function Onboarding() {
  const { addCompany, signOut } = useStore()
  const nav = useNavigate()
  return (
    <main className="min-h-dvh bg-canvas px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex items-center gap-2 text-fg-2">
          <LogoMark />
          <span className="font-medium">{PRODUCT_NAME}</span>
        </div>
        <h1 className="text-2xl font-semibold">Which company should we protect?</h1>
        <p className="mt-1 mb-8 text-fg-2">We use this to find mentions and tell real criticism apart from attacks. Takes about a minute.</p>
        <section className="rounded-panel border border-line bg-surface p-6">
          <CompanyWizard
            onDone={c => { addCompany(c); nav('/app/feed', { replace: true }) }}
            aside={
              <Button type="button" variant="ghost" className="-ml-3" onClick={() => { signOut(); nav('/login', { replace: true }) }}>
                <SignOut size={16} /> Sign out
              </Button>
            }
          />
        </section>
      </div>
    </main>
  )
}
