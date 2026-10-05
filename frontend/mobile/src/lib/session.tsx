import type { Session } from '@supabase/supabase-js'
import { makeRedirectUri } from 'expo-auth-session'
import * as Linking from 'expo-linking'
import * as WebBrowser from 'expo-web-browser'
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { registerForPush, unregisterForPush } from './push'
import { supabase } from './supabase'

WebBrowser.maybeCompleteAuthSession() // closes the auth popup when running on web

// palladion:// in builds, exp://localhost:8081 in Expo Go; both must be in Supabase's redirect allow list.
// preferLocalhost: Supabase rejects redirect hosts that are non-loopback IPs (Expo Go's default
// exp://<LAN IP>) before checking the allow list. The auth session matches the callback by scheme only.
const redirectTo = makeRedirectUri({ preferLocalhost: true })

interface SessionState {
  session: Session | null | undefined // undefined while the stored session is restored
  authError: string | null
  signIn: () => Promise<void>
  signOut: (reason?: string) => void
}

const Ctx = createContext<SessionState | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null | undefined>(undefined)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  // Once per signed-in account; outside the auth callback, which holds Supabase's session lock
  const userId = session?.user.id
  useEffect(() => {
    if (userId) registerForPush().catch((e: unknown) => console.warn('Push registration failed', e))
  }, [userId])

  // Same Google sign-in as the web app, through the in-app browser instead of a page redirect
  async function signIn() {
    setAuthError(null)
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo, skipBrowserRedirect: true },
    })
    if (error || !data.url) return setAuthError(error?.message ?? 'Could not start Google sign-in')

    const res = await WebBrowser.openAuthSessionAsync(data.url, redirectTo)
    if (res.type !== 'success') return // closed by the user

    const { code, error_description } = Linking.parse(res.url).queryParams ?? {}
    if (typeof code !== 'string') return setAuthError(typeof error_description === 'string' ? error_description : 'Google sign-in failed')
    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)
    if (exchangeError) setAuthError(exchangeError.message)
  }

  // Stable, so screens can use it as an effect dependency
  const signOut = useCallback((reason?: string) => {
    setAuthError(reason ?? null)
    // Best effort: with a rejected token the backend refuses this too, and the session still has to end
    void unregisterForPush().catch(() => {}).finally(() => supabase.auth.signOut())
  }, [])

  return <Ctx.Provider value={{ session, authError, signIn, signOut }}>{children}</Ctx.Provider>
}

export function useSession() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useSession must be used inside SessionProvider')
  return ctx
}
