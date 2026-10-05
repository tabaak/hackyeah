import { router } from 'expo-router'
import { Check } from 'phosphor-react-native'
import { Pressable, StyleSheet, View } from 'react-native'
import { T } from '../components/ui'
import { radius, THEMES, useTheme, type Theme } from '../lib/theme'

// Same swatches as THEME_META in frontend/web/src/pages/AppShell.tsx
const THEME_META: Record<Theme, { label: string; swatch: [string, string] }> = {
  graphite: { label: 'Graphite', swatch: ['#202020', '#737373'] },
  navy: { label: 'Navy', swatch: ['#111827', '#64748b'] },
  laurel: { label: 'Laurel', swatch: ['#11241e', '#5a8075'] },
  light: { label: 'Light', swatch: ['#ffffff', '#e2e8f0'] },
}

export default function Settings() {
  const { theme, setTheme, colors: c } = useTheme()
  return (
    <View style={s.screen}>
      <View style={[s.panel, { borderColor: c.line, backgroundColor: c.surface }]}>
        {THEMES.map(t => (
          <Pressable
            key={t}
            onPress={() => { setTheme(t); router.back() }}
            accessibilityRole="button"
            accessibilityState={{ selected: theme === t }}
            style={({ pressed }) => [s.option, pressed && { backgroundColor: c.subtle }]}
          >
            {/* Diagonal two-tone swatch, as on web */}
            <View style={[s.swatch, { borderColor: c.line, backgroundColor: THEME_META[t].swatch[0] }]}>
              <View style={[s.swatchHalf, { backgroundColor: THEME_META[t].swatch[1] }]} />
            </View>
            <T>{THEME_META[t].label}</T>
            {theme === t && <Check size={16} color={c.accent} style={s.check} />}
          </Pressable>
        ))}
      </View>
    </View>
  )
}

const s = StyleSheet.create({
  screen: { flex: 1, padding: 16 },
  panel: { borderWidth: 1, borderRadius: radius.dialog, padding: 4 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44, paddingHorizontal: 10, borderRadius: radius.control },
  // Rotated 45° so the right half becomes the bottom-right half of a 135° split
  swatch: { width: 24, height: 24, borderRadius: 12, borderWidth: 1, overflow: 'hidden', transform: [{ rotate: '45deg' }] },
  swatchHalf: { position: 'absolute', top: 0, bottom: 0, left: 11, right: 0 },
  check: { marginLeft: 'auto' },
})
