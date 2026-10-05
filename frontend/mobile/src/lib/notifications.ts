import { api } from './api'

export { ApiError } from './api'

// Mirrors backend/app/schemas/notifications.py (camelCase over the wire).
export type Severity = 'high' | 'medium' | 'low'
export type NotificationKind = 'critical_mention' | 'approval_requested' | 'approval_decided'

export interface Notification {
  id: string
  kind: NotificationKind
  mentionId: string | null
  title: string
  severity: Severity
  at: number // Unix ms
  read: boolean
}

export interface NotificationList {
  items: Notification[]
  openCount: number
}

export const KIND_LABEL: Record<NotificationKind, string> = {
  critical_mention: 'Critical mention',
  approval_requested: 'Approval requested',
  approval_decided: 'Approval decided',
}

export const listNotifications = () => api<NotificationList>('/notifications?limit=50')
export const markRead = (id: string) => api<Notification>(`/notifications/${id}/read`, { method: 'PATCH' })
export const markAllRead = () => api<void>('/notifications/mark-all-read', { method: 'POST' })
