import * as Notifications from 'expo-notifications'
import { Link } from 'expo-router'
import { Checks, Palette, SealCheck, ShieldWarning, SignOut, UserCheck } from 'phosphor-react-native'
import { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, AppState, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Button, LogoMark, PRODUCT_NAME, SeverityBadge, T, timeAgo } from '../components/ui'
import { ApiError, KIND_LABEL, listNotifications, markAllRead, markRead, type Notification, type NotificationKind } from '../lib/notifications'
import { useSession } from '../lib/session'
import { font, radius, useTheme } from '../lib/theme'

const KIND_ICON: Record<NotificationKind, typeof ShieldWarning> = {
  critical_mention: ShieldWarning,
  approval_requested: UserCheck,
  approval_decided: SealCheck,
}

type Filter = 'all' | 'unread'

const POLL_MS = 12_000 // same cadence as the web bell (Endpoints.md: poll every 10-15 s)

function Header() {
  const { colors: c } = useTheme()
  const { signOut } = useSession()
  const { top } = useSafeAreaInsets()
  return (
    <View style={[s.header, { backgroundColor: c.sidebar, paddingTop: top + 12 }]}>
      <LogoMark />
      <Text style={[s.brand, { color: c.sidebarText }]}>{PRODUCT_NAME}</Text>
      <View style={s.spacer} />
      <Link href="/settings" asChild>
        <Pressable accessibilityRole="button" accessibilityLabel="Change theme" hitSlop={4} style={({ pressed }) => [s.iconButton, pressed && { backgroundColor: c.sidebarActive }]}>
          <Palette size={20} color={c.sidebarMuted} />
        </Pressable>
      </Link>
      <Pressable onPress={() => signOut()} accessibilityRole="button" accessibilityLabel="Sign out" hitSlop={4} style={({ pressed }) => [s.iconButton, pressed && { backgroundColor: c.sidebarActive }]}>
        <SignOut size={20} color={c.sidebarMuted} />
      </Pressable>
    </View>
  )
}

function Row({ n, onPress }: { n: Notification; onPress: () => void }) {
  const { colors: c } = useTheme()
  const Icon = KIND_ICON[n.kind]
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${n.read ? '' : 'Unread. '}${KIND_LABEL[n.kind]}: ${n.title}`}
      style={({ pressed }) => [s.row, { backgroundColor: pressed ? c.subtle : c.surface }]}
    >
      {/* Unread marker: the sidebar's active-tab bar */}
      {!n.read && <View style={[s.unreadBar, { backgroundColor: c.accent }]} />}
      <View style={s.meta}>
        <Icon size={14} color={n.kind === 'critical_mention' ? c.danger : c.fg3} />
        <T tone="fg3" style={s.small}>{KIND_LABEL[n.kind]}</T>
        <T tone="fg3" style={[s.small, s.push]}>{timeAgo(n.at)}</T>
      </View>
      {/* Read items recede to secondary grey; unread stay bright and medium weight */}
      <T numberOfLines={2} tone={n.read ? 'fg2' : 'fg'} style={!n.read && { fontFamily: font.sansMedium }}>{n.title}</T>
      <View style={s.badges}><SeverityBadge s={n.severity} /></View>
    </Pressable>
  )
}

export default function Inbox() {
  const { colors: c } = useTheme()
  const { signOut } = useSession()
  const [items, setItems] = useState<Notification[] | null>(null) // null until the first load
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [refreshing, setRefreshing] = useState(false)
  const all = items ?? []
  const unread = all.filter(n => !n.read).length
  const shown = filter === 'unread' ? all.filter(n => !n.read) : all

  const load = useCallback(async () => {
    try {
      setItems((await listNotifications()).items)
      setError(null)
    } catch (e) {
      // Same rule as the web store: a rejected token or unprovisioned profile ends the session
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return signOut(e.message)
      setError(e instanceof Error ? e.message : 'Could not load notifications')
    }
  }, [signOut])

  // Poll while the app is in the foreground; reload as soon as it comes back
  useEffect(() => {
    void load()
    let timer = setInterval(load, POLL_MS)
    const sub = AppState.addEventListener('change', state => {
      clearInterval(timer)
      if (state !== 'active') return
      void load()
      timer = setInterval(load, POLL_MS)
    })
    // A push arriving while the app is open: show it in the list right away
    const pushed = Notifications.addNotificationReceivedListener(() => void load())
    return () => {
      clearInterval(timer)
      sub.remove()
      pushed.remove()
    }
  }, [load])

  // Optimistic; on failure the server state is reloaded
  const read = (n: Notification) => {
    if (n.read) return
    setItems(xs => xs && xs.map(x => (x.id === n.id ? { ...x, read: true } : x)))
    markRead(n.id).catch(load)
  }
  const readAll = () => {
    setItems(xs => xs && xs.map(x => ({ ...x, read: true })))
    markAllRead().catch(load)
  }
  const refresh = async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }

  return (
    <View style={[s.screen, { backgroundColor: c.canvas }]}>
      <Header />
      <FlatList
        data={shown}
        keyExtractor={n => n.id}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.accent} colors={[c.accent]} />}
        ListHeaderComponent={
          <View style={s.titleBlock}>
            <View style={s.titleRow}>
              <Text style={[s.title, { color: c.fg }]}>Notifications</Text>
              <Button variant="ghost" onPress={readAll} disabled={unread === 0} icon={<Checks size={18} color={c.fg2} />}>Mark all read</Button>
            </View>
            <View style={[s.segment, { borderColor: c.line, backgroundColor: c.surface }]} accessibilityRole="tablist">
              {(['all', 'unread'] as const).map(f => (
                <Pressable
                  key={f}
                  onPress={() => setFilter(f)}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: filter === f }}
                  style={[s.segmentItem, filter === f && { backgroundColor: c.selected }]}
                >
                  <T tone={filter === f ? 'fg' : 'fg2'} style={filter === f && { fontFamily: font.sansMedium }}>
                    {f === 'all' ? 'All' : `Unread · ${unread}`}
                  </T>
                </Pressable>
              ))}
            </View>
            {/* Stale list stays visible; polling retries */}
            {error && items && <T style={[s.small, { color: c.danger }]}>Couldn’t refresh: {error}</T>}
          </View>
        }
        ItemSeparatorComponent={() => <View style={[s.divider, { backgroundColor: c.line }]} />}
        renderItem={({ item, index }) => (
          <View
            style={[
              s.cell,
              { borderColor: c.line },
              index === 0 && s.first,
              index === shown.length - 1 && s.last,
            ]}
          >
            <Row n={item} onPress={() => read(item)} />
          </View>
        )}
        ListEmptyComponent={
          <View style={[s.empty, { borderColor: c.line, backgroundColor: c.surface }]}>
            {items ? (
              <T tone="fg3" style={s.center}>{filter === 'unread' ? 'You’re all caught up.' : 'No notifications yet.'}</T>
            ) : error ? (
              <>
                <T style={[s.center, { color: c.danger }]}>{error}</T>
                <Button onPress={refresh}>Try again</Button>
              </>
            ) : (
              <ActivityIndicator color={c.accent} />
            )}
          </View>
        }
      />
    </View>
  )
}

const s = StyleSheet.create({
  screen: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingBottom: 12 },
  brand: { fontFamily: font.display, fontSize: 24, lineHeight: 28, letterSpacing: -0.3, transform: [{ translateY: 3 }] },
  spacer: { flex: 1 },
  iconButton: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: radius.control },
  content: { padding: 16, paddingBottom: 40 },
  titleBlock: { marginBottom: 16, gap: 16 },
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontFamily: font.display, fontSize: 24, lineHeight: 28, letterSpacing: -0.3 },
  segment: { flexDirection: 'row', borderWidth: 1, borderRadius: radius.control, padding: 2 },
  segmentItem: { flex: 1, minHeight: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radius.control - 2 },
  // List rendered as one bordered panel with dividers, like the web notifications popover
  cell: { borderLeftWidth: 1, borderRightWidth: 1, overflow: 'hidden' },
  first: { borderTopWidth: 1, borderTopLeftRadius: radius.dialog, borderTopRightRadius: radius.dialog },
  last: { borderBottomWidth: 1, borderBottomLeftRadius: radius.dialog, borderBottomRightRadius: radius.dialog },
  divider: { height: StyleSheet.hairlineWidth, marginHorizontal: 1 },
  row: { paddingHorizontal: 16, paddingVertical: 12, gap: 6 },
  unreadBar: { position: 'absolute', left: 0, top: 8, bottom: 8, width: 2, borderRadius: 999 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  small: { fontSize: 12, lineHeight: 16 },
  push: { marginLeft: 'auto' },
  badges: { flexDirection: 'row', gap: 6, marginTop: 2 },
  empty: { borderWidth: 1, borderRadius: radius.dialog, paddingVertical: 24, paddingHorizontal: 16, gap: 12, alignItems: 'center' },
  center: { textAlign: 'center' },
})
