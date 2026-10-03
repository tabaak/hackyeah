import { useStore } from '../lib/store'
import { Button } from '../lib/ui'
import { LogoMark, PRODUCT_NAME } from '../pages/Login'

export default function SessionLoading() {
  const { sessionError, retrySession, signOut } = useStore()
  return (
    <main className="flex min-h-dvh items-center justify-center px-4">
      <section className="w-full max-w-sm rounded-panel border border-line bg-surface p-6">
        <div className="mb-5 flex items-center gap-3">
          <LogoMark />
          <span className="font-display text-[28px] font-medium">{PRODUCT_NAME}</span>
        </div>
        {sessionError ? (
          <>
            <p role="alert" className="text-sm text-fg-2">{sessionError}</p>
            <div className="mt-5 flex gap-2">
              <Button variant="primary" onClick={retrySession}>Try again</Button>
              <Button variant="ghost" onClick={signOut}>Sign out</Button>
            </div>
          </>
        ) : <p role="status" className="text-sm text-fg-2">Loading your workspace…</p>}
      </section>
    </main>
  )
}
