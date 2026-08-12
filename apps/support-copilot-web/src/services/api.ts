import type { AnalysisResult, Metrics, Ticket } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

type ApiErrorPayload = {
  code?: string
  message?: string
  traceId?: string
  details?: Record<string, unknown>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseApiErrorPayload(value: unknown): ApiErrorPayload {
  if (!isRecord(value)) return {}

  return {
    code: typeof value.code === 'string' ? value.code : undefined,
    message: typeof value.message === 'string' ? value.message : undefined,
    traceId: typeof value.traceId === 'string' ? value.traceId : undefined,
    details: isRecord(value.details) ? value.details : undefined,
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly traceId: string | null
  readonly details: Record<string, unknown>

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message ?? `API request failed: ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code ?? `HTTP_${status}`
    this.traceId = payload.traceId ?? null
    this.details = payload.details ?? {}
  }
}

// 这里是浏览器侧的 API 边界。
// React 组件只调用这些小函数，不需要直接关心后端地址、HTTP 方法和响应解析细节。
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  // 只有 2xx 响应才代表请求成功；409、404、500 等状态都要进入错误分支。
  if (!response.ok) {
    // 错误响应也可能带有业务代码和 traceId，先读取它们再交给调用方。
    const payload: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, parseApiErrorPayload(payload))
  }

  return response.json() as Promise<T>
}

export function fetchTickets(signal?: AbortSignal) {
  return request<Ticket[]>('/api/tickets', { signal })
}

export function fetchMetrics(signal?: AbortSignal) {
  return request<Metrics>('/api/metrics', { signal })
}

export function analyzeTicket(ticketId: string) {
  return request<AnalysisResult>(`/api/tickets/${ticketId}/analyze`, {
    method: 'POST',
  })
}

export function updateTicket(
  ticketId: string,
  update: Partial<Pick<Ticket, 'status' | 'priority' | 'category' | 'assigneeName'>>,
) {
  return request<Ticket>(`/api/tickets/${ticketId}`, {
    method: 'PATCH',
    body: JSON.stringify(update),
  })
}

export function unassignTicket(ticketId: string, expectedVersion: number) {
  return request<Ticket>(`/api/tickets/${ticketId}/unassign`, {
    method: 'POST',
    body: JSON.stringify({ expectedVersion }),
  })
}
