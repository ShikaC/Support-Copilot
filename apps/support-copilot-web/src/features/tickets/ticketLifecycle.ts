import type { PersistedTicketStatus } from '../../types'

export const manualTransitions: Readonly<Record<PersistedTicketStatus, readonly PersistedTicketStatus[]>> = {
  NEW: ['IN_PROGRESS'], READY_FOR_REVIEW: ['IN_PROGRESS'], READY_FOR_MANUAL_REVIEW: ['IN_PROGRESS'],
  NEEDS_ESCALATION: ['IN_PROGRESS'], IN_PROGRESS: ['WAITING_CUSTOMER', 'RESOLVED'],
  WAITING_CUSTOMER: ['IN_PROGRESS'], RESOLVED: ['CLOSED'], CLOSED: [],
}
export const transitionLabels: Readonly<Partial<Record<PersistedTicketStatus, string>>> = {
  IN_PROGRESS: '开始处理', WAITING_CUSTOMER: '等待客户', RESOLVED: '标记为已解决', CLOSED: '关闭工单',
}
export function isTerminal(status: PersistedTicketStatus) { return status === 'RESOLVED' || status === 'CLOSED' }
