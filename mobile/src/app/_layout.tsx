import { IBMPlexMono_400Regular } from '@expo-google-fonts/ibm-plex-mono'
import { IBMPlexSans_400Regular, IBMPlexSans_500Medium, IBMPlexSans_600SemiBold } from '@expo-google-fonts/ibm-plex-sans'
import { Newsreader_500Medium } from '@expo-google-fonts/newsreader'
import { useFonts } from 'expo-font'
import { Stack } from 'expo-router'
import * as SplashScreen from 'expo-splash-screen'
import { StatusBar } from 'expo-status-bar'
import { useEffect, useMemo, useState } from 'react'
import { SessionProvider, useSession } from '../lib/session'
import { font, isDark, PALETTES, ThemeContext, type Theme } from '../lib/theme'

SplashScreen.preventAutoHideAsync()

export default function RootLayout() {
  return (
    <SessionProvider>
      <App />
    </SessionProvider>
  )
}

function App() {
  const { session } = useSession()
  const [loaded, error] = useFonts({
    IBMPlexSans_400Regular, IBMPlexSans_500Medium, IBMPlexSans_600SemiBold, IBMPlexMono_400Regular, Newsreader_500Medium,
  })
  const [theme, setTheme] = useState<Theme>('graphite') // same default as the web app
  const value = useMemo(() => ({ theme, colors: PALETTES[theme], setTheme }), [theme])

  // Keep the splash up until fonts are in and the stored session is restored, so the login screen never flashes
  const ready = (loaded || !!error) && session !== undefined
  useEffect(() => {
    if (ready) SplashScreen.hideAsync()
  }, [ready])

  if (!ready) return null

  const c = value.colors
  return (
    <ThemeContext.Provider value={value}>
      {/* Signed in, the header is always the dark sidebar colour, as on web; login sits on the canvas */}
      <StatusBar style={session || isDark(theme) ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: c.sidebar },
          headerTintColor: c.sidebarText,
          headerTitleStyle: { fontFamily: font.sansSemibold, fontSize: 16 },
          headerShadowVisible: false,
          contentStyle: { backgroundColor: c.canvas },
        }}
      >
        <Stack.Protected guard={!!session}>
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="settings" options={{ title: 'Appearance', presentation: 'modal' }} />
        </Stack.Protected>
        <Stack.Protected guard={!session}>
          <Stack.Screen name="login" options={{ headerShown: false }} />
        </Stack.Protected>
      </Stack>
    </ThemeContext.Provider>
  )
}
