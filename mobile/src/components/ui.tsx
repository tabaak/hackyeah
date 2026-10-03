// Native counterparts of frontend/src/lib/ui.tsx: same variants, tones and sizes.
import { Warning } from 'phosphor-react-native'
import type { ReactNode } from 'react'
import { Image, Pressable, StyleSheet, Text, View, type PressableProps, type StyleProp, type TextProps, type ViewStyle } from 'react-native'
import type { Severity } from '../lib/notifications'
import { font, radius, useTheme, type Colors } from '../lib/theme'

export const PRODUCT_NAME = 'Palladion'

export function LogoMark({ height = 32 }: { height?: number }) {
  // Source PNG is 136×406
  return <Image source={require('../../assets/images/logo-figure.png')} style={{ height, width: (height * 136) / 406 }} accessibilityIgnoresInvertColors />
}

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
const variantStyle = (v: Variant, c: Colors, pressed: boolean): ViewStyle => ({
  primary: { backgroundColor: pressed ? c.accentHover : c.accent },
  secondary: { borderWidth: 1, borderColor: c.control, backgroundColor: pressed ? c.subtle : 'transparent' },
  ghost: { backgroundColor: pressed ? c.subtle : 'transparent' },
  danger: { borderWidth: 1, borderColor: c.danger, backgroundColor: c.dangerBg },
})[v]
const variantText = (v: Variant, c: Colors) => ({ primary: c.onAccent, secondary: c.fg, ghost: c.fg2, danger: c.danger })[v]

export function Button({ variant = 'secondary', icon, children, style, disabled, ...p }: Omit<PressableProps, 'children' | 'style'> & {
  variant?: Variant
  icon?: ReactNode
  children?: ReactNode
  style?: StyleProp<ViewStyle>
}) {
  const { colors } = useTheme()
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      {...p}
      style={({ pressed }) => [s.button, variantStyle(variant, colors, pressed), pressed && s.pressed, disabled && s.disabled, style]}
    >
      {icon}
      {children != null && <Text style={[s.buttonText, { color: variantText(variant, colors) }]}>{children}</Text>}
    </Pressable>
  )
}

export type Tone = 'neutral' | 'danger' | 'warning' | 'info' | 'success' | 'ready'
const toneColors = (t: Tone, c: Colors) => ({
  neutral: [c.subtle, c.neutral],
  danger: [c.dangerBg, c.danger],
  warning: [c.warningBg, c.warning],
  info: [c.infoBg, c.info],
  success: [c.successBg, c.success],
  ready: [c.readyBg, c.ready],
})[t]

export function Badge({ tone = 'neutral', icon, children }: { tone?: Tone; icon?: (color: string) => ReactNode; children: ReactNode }) {
  const { colors } = useTheme()
  const [bg, fg] = toneColors(tone, colors)
  return (
    <View style={[s.badge, { backgroundColor: bg }]}>
      {icon?.(fg)}
      <Text style={[s.badgeText, { color: fg }]}>{children}</Text>
    </View>
  )
}

export function SeverityBadge({ s: sev }: { s: Severity }) {
  if (sev === 'high') return <Badge tone="danger" icon={c => <Warning size={12} weight="bold" color={c} />}>High</Badge>
  if (sev === 'medium') return <Badge tone="warning">Medium</Badge>
  return <Badge>Low</Badge>
}

// Text with the app's body defaults (14/20, IBM Plex Sans); `tone` picks fg / fg-2 / fg-3
export function T({ tone = 'fg', style, ...p }: TextProps & { tone?: 'fg' | 'fg2' | 'fg3' }) {
  const { colors } = useTheme()
  return <Text {...p} style={[s.body, { color: colors[tone] }, style]} />
}

export function timeAgo(t: number) {
  const m = Math.round((Date.now() - t) / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`
}

const s = StyleSheet.create({
  body: { fontFamily: font.sans, fontSize: 14, lineHeight: 20, fontVariant: ['tabular-nums'] },
  button: { minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: radius.control, paddingHorizontal: 12 },
  buttonText: { fontFamily: font.sansMedium, fontSize: 14, lineHeight: 20 },
  pressed: { transform: [{ translateY: 1 }] },
  disabled: { opacity: 0.5 },
  badge: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  badgeText: { fontFamily: font.sansMedium, fontSize: 12, lineHeight: 16 },
})
