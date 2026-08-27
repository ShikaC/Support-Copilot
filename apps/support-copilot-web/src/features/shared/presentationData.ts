import type { AnalysisResult, Priority, TicketStatus } from '../../types'

export const categoryLabels: Readonly<Record<string, string>> = {
  UNCLASSIFIED: '未分类', GENERAL: '一般咨询', BILLING: '账单支付',
  ACCOUNT_ACCESS: '账号访问', INVOICE: '发票服务', DATA_EXPORT: '数据导出',
  SUBSCRIPTION: '订阅咨询', PRIVACY: '隐私合规', SECURITY: '安全事件',
  LEGAL: '法务请求', TECHNICAL: '技术问题', DATA_RECOVERY: '数据恢复',
}
export const priorityLabels: Readonly<Record<Priority, string>> = {
  URGENT: '紧急', HIGH: '高', MEDIUM: '中', LOW: '低',
}
export const statusLabels: Readonly<Record<TicketStatus, string>> = {
  NEW: '新工单', ANALYZING: '分析中', READY_FOR_REVIEW: '待审核', IN_PROGRESS: '处理中',
  NEEDS_ESCALATION: '需升级', WAITING_CUSTOMER: '等待客户', RESOLVED: '已解决',
  CLOSED: '已关闭', READY_FOR_MANUAL_REVIEW: '人工复核',
}
export const statusColors: Readonly<Record<TicketStatus, string>> = {
  NEW: 'blue', ANALYZING: 'gold', READY_FOR_REVIEW: 'cyan', IN_PROGRESS: 'processing',
  NEEDS_ESCALATION: 'red', WAITING_CUSTOMER: 'orange', RESOLVED: 'green',
  CLOSED: 'default', READY_FOR_MANUAL_REVIEW: 'volcano',
}
export const sentimentLabels: Readonly<Record<AnalysisResult['classification']['sentiment'], string>> = {
  POSITIVE: '正向', NEUTRAL: '中性', NEGATIVE: '负向',
}

export function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}
export function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}
export function formatTicketDescription(value: string) {
  return value.replace(/(\d)\s+([年月日])/g, '$1\u00a0$2')
}
export function secondsUntil(value: string) {
  return Math.floor((new Date(value).getTime() - Date.now()) / 1000)
}
export function slaLabel(value: string) {
  const seconds = secondsUntil(value)
  if (seconds <= 0) return 'SLA 已超时'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.max(0, Math.floor((seconds % 3600) / 60))
  return hours > 0 ? `${hours}小时${minutes}分` : `${minutes}分钟`
}
