// Ported 1:1 from frontend/src/index.css (TEST_DESIGN.md §3.6). Keep the two in sync.
import { createContext, useContext } from 'react'

export type Theme = 'graphite' | 'navy' | 'laurel' | 'light'
export const THEMES: Theme[] = ['graphite', 'navy', 'laurel', 'light']

const light = {
  canvas: '#f7f9fa',
  surface: '#ffffff',
  subtle: '#f1f5f9',
  sidebar: '#171717',
  sidebarActive: '#262626',
  sidebarText: '#f5f5f5',
  sidebarMuted: '#a3a3a3',
  sidebarAccent: '#5eead4',
  fg: '#0f172a',
  fg2: '#475569',
  fg3: '#64748b',
  line: '#e2e8f0',
  control: '#64748b',
  accent: '#0f766e',
  accentHover: '#115e59',
  onAccent: '#ffffff',
  selected: '#eef6f5',
  danger: '#b42318',
  dangerBg: '#fef3f2',
  warning: '#92400e',
  warningBg: '#fffbeb',
  info: '#1d4ed8',
  infoBg: '#eff6ff',
  success: '#166534',
  successBg: '#f0fdf4',
  ready: '#115e59',
  readyBg: '#f0fdfa',
  neutral: '#334155',
}

export type Colors = typeof light

const graphite: Colors = {
  canvas: '#171717',
  surface: '#202020',
  subtle: '#292929',
  sidebar: '#111111',
  sidebarActive: '#292929',
  sidebarText: '#f5f5f5',
  sidebarMuted: '#a3a3a3',
  sidebarAccent: '#5eead4',
  fg: '#f5f5f5',
  fg2: '#d4d4d4',
  fg3: '#a3a3a3',
  line: '#363636',
  control: '#737373',
  accent: '#2dd4bf',
  accentHover: '#5eead4',
  onAccent: '#042f2e',
  selected: '#0f2b2a',
  danger: '#fca5a5',
  dangerBg: '#3a1214',
  warning: '#fcd34d',
  warningBg: '#36270a',
  info: '#93c5fd',
  infoBg: '#142046',
  success: '#86efac',
  successBg: '#0a2e1a',
  ready: '#5eead4',
  readyBg: '#062a28',
  neutral: '#d4d4d4',
}

// Dark variants override graphite surfaces; status colors are shared
const navy: Colors = {
  ...graphite,
  canvas: '#0b1120',
  surface: '#111827',
  subtle: '#1a2333',
  sidebar: '#060a14',
  sidebarActive: '#1a2333',
  sidebarText: '#f1f5f9',
  sidebarMuted: '#94a3b8',
  fg: '#f1f5f9',
  fg2: '#cbd5e1',
  fg3: '#94a3b8',
  line: '#233046',
  control: '#64748b',
  neutral: '#cbd5e1',
}

// Laurel: deep green-black around the brand's statue green
const laurel: Colors = {
  ...graphite,
  canvas: '#0b1a16',
  surface: '#11241e',
  subtle: '#183129',
  sidebar: '#07120f',
  sidebarActive: '#183129',
  sidebarText: '#eef3f0',
  sidebarMuted: '#8fb0a4',
  sidebarAccent: '#6ee0c2',
  fg: '#eef3f0',
  fg2: '#c6dbd3',
  fg3: '#8fb0a4',
  line: '#21403a',
  control: '#5a8075',
  accent: '#3cc9a6',
  accentHover: '#6ee0c2',
  onAccent: '#04261d',
  selected: '#123a31',
  ready: '#6ee0c2',
  readyBg: '#0b2b24',
  neutral: '#c6dbd3',
}

export const PALETTES: Record<Theme, Colors> = { graphite, navy, laurel, light }

export const isDark = (t: Theme) => t !== 'light'

export const radius = { control: 6, panel: 8, dialog: 10 }

// Loaded in src/app/_layout.tsx; RN needs one family name per weight
export const font = {
  sans: 'IBMPlexSans_400Regular',
  sansMedium: 'IBMPlexSans_500Medium',
  sansSemibold: 'IBMPlexSans_600SemiBold',
  mono: 'IBMPlexMono_400Regular',
  display: 'Newsreader_500Medium',
}

export const ThemeContext = createContext<{ theme: Theme; colors: Colors; setTheme: (t: Theme) => void }>({
  theme: 'graphite',
  colors: graphite,
  setTheme: () => {},
})

export const useTheme = () => useContext(ThemeContext)
