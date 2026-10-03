import { useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import Svg, { Path } from 'react-native-svg'
import { LogoMark, PRODUCT_NAME, T } from '../components/ui'
import { useSession } from '../lib/session'
import { font, radius, useTheme } from '../lib/theme'

// Same mark and copy as frontend/src/pages/Login.tsx
function GoogleIcon() {
  return (
    <Svg width={20} height={20} viewBox="0 0 48 48">
      <Path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z" />
      <Path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <Path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <Path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z" />
    </Svg>
  )
}

export default function Login() {
  const { signIn, authError } = useSession()
  const { colors: c } = useTheme()
  const [pending, setPending] = useState(false)

  async function go() {
    setPending(true)
    await signIn()
    setPending(false)
  }

  return (
    <SafeAreaView style={[s.screen, { backgroundColor: c.canvas }]}>
      <View style={s.content}>
        <View style={s.logo}>
          <LogoMark height={64} />
          <Text style={[s.brand, { color: c.fg2 }]}>{PRODUCT_NAME}</Text>
        </View>
        <Text style={[s.headline, { color: c.fg }]}>Catch the attack before it trends</Text>
        <T tone="fg2" style={s.lead}>Critical mentions and approval requests from your workspace, as they happen</T>
        <Pressable
          onPress={go}
          disabled={pending}
          accessibilityRole="button"
          style={({ pressed }) => [s.google, { borderColor: c.line }, pressed && s.googlePressed, pending && s.disabled]}
        >
          {pending ? <ActivityIndicator color="#1f1f1f" /> : <GoogleIcon />}
          <Text style={s.googleText}>{pending ? 'Signing in…' : 'Continue with Google'}</Text>
        </Pressable>
        {authError && <T accessibilityRole="alert" style={[s.error, { color: c.danger }]}>{authError}</T>}
      </View>
    </SafeAreaView>
  )
}

const s = StyleSheet.create({
  screen: { flex: 1 },
  content: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 24 },
  logo: { alignItems: 'center', gap: 12 },
  brand: { fontFamily: font.display, fontSize: 20, lineHeight: 28 },
  headline: { marginTop: 32, fontFamily: font.display, fontSize: 44, lineHeight: 46, letterSpacing: -0.9, textAlign: 'center' },
  lead: { marginTop: 20, maxWidth: 340, fontSize: 17, lineHeight: 26, textAlign: 'center' },
  google: {
    marginTop: 40, width: '100%', maxWidth: 320, height: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 12,
    borderWidth: 1, borderRadius: radius.control, backgroundColor: '#ffffff',
  },
  googlePressed: { backgroundColor: '#f2f2f2', transform: [{ translateY: 1 }] },
  disabled: { opacity: 0.6 },
  googleText: { fontFamily: font.sansMedium, fontSize: 16, color: '#1f1f1f' },
  error: { marginTop: 16, textAlign: 'center' },
})
