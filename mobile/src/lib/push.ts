import Constants from 'expo-constants'
import * as Notifications from 'expo-notifications'
import { Platform } from 'react-native'
import { api } from './api'

// Show critical alerts even while the app is open
Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
})

let registered: string | null = null // token sent to the backend for the current account

// Asks for permission, then gives the backend this device's Expo push token. Safe to call on every sign-in.
export async function registerForPush(): Promise<void> {
  if (Platform.OS === 'android') {
    // Must match channelId in backend/app/services/push.py
    await Notifications.setNotificationChannelAsync('critical', {
      name: 'Critical mentions',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
    })
  }
  const current = await Notifications.getPermissionsAsync()
  const { status } = current.granted ? current : await Notifications.requestPermissionsAsync()
  if (status !== 'granted') return

  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId
  if (!projectId) {
    console.warn('Push disabled: no EAS project id. Run `npx eas-cli init` in mobile/.')
    return
  }
  const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId })
  await api<void>('/push-tokens', { method: 'POST', body: JSON.stringify({ token, platform: Platform.OS }) })
  registered = token
}

// Before sign-out, while the session is still valid, so this device stops getting the old account's alerts
export async function unregisterForPush(): Promise<void> {
  if (!registered) return
  const token = registered
  registered = null
  await api<void>(`/push-tokens/${encodeURIComponent(token)}`, { method: 'DELETE' })
}
