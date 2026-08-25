import type * as z from 'zod'

import type { AnalysisResult, Ticket } from '../types'
import {
  analysisReviewSchema,
  analysisResultSchema,
  metricsResponseSchema,
  ticketResponseListSchema,
  ticketResponseSchema,
} from './apiSchemas'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const inFlightAnalyses = new Map<string, Promise<AnalysisResult>>()

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
  readonly name = 'ApiError'
  readonly status: number
  readonly code: string
  readonly traceId: string | null
  readonly details: Record<string, unknown>

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message ?? `API request failed: ${status}`)
    this.status = status
    this.code = payload.code ?? `HTTP_${status}`
    this.traceId = payload.traceId ?? null
    this.details = payload.details ?? {}
  }
}

export type ApiContractIssue = {
  readonly path: string
  readonly code: string
}

export class ApiContractError extends Error {
  readonly name = 'ApiContractError'
  readonly path: string
  readonly issues: readonly ApiContractIssue[]

  constructor(path: string, issues: readonly ApiContractIssue[]) {
    super(`API response contract mismatch for ${path}: ${issues.map((issue) => issue.path).join(', ')}`)
    this.path = path
    this.issues = issues
  }
}

// 这里是浏览器侧的 API 边界。
// React 组件只调用这些小函数，不需要直接关心后端地址、HTTP 方法和响应解析细节。
async function request<Schema extends z.ZodType>(
  path: string,
  schema: Schema,
  init?: RequestInit,
): Promise<z.output<Schema>> {
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

  let payload: unknown
  try {
    payload = await response.json()
  } catch (error: unknown) {
    if (error instanceof SyntaxError) {
      throw new ApiContractError(path, [{ path: '$', code: 'invalid_json' }])
    }
    throw error
  }

  const parsed = schema.safeParse(payload)
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => ({
      path: issue.path.length === 0 ? '$' : issue.path.join('.'),
      code: issue.code,
    }))
    throw new ApiContractError(path, issues)
  }
  return parsed.data
}

export function fetchTickets(signal?: AbortSignal) {
  return request('/api/tickets', ticketResponseListSchema, { signal })
}

export function fetchMetrics(signal?: AbortSignal) {
  return request('/api/metrics', metricsResponseSchema, { signal })
}

export function analyzeTicket(ticketId: string) {
  const existing = inFlightAnalyses.get(ticketId)
  if (existing) return existing

  const pending = request(`/api/tickets/${ticketId}/analyze`, analysisResultSchema, {
    method: 'POST',
  })
  const tracked = pending.finally(() => {
    if (inFlightAnalyses.get(ticketId) === tracked) {
      inFlightAnalyses.delete(ticketId)
    }
  })
  inFlightAnalyses.set(ticketId, tracked)
  return tracked
}

export function updateTicket(
  ticketId: string,
  update: Partial<Pick<Ticket, 'status' | 'priority' | 'category' | 'assigneeName'>>,
) {
  return request(`/api/tickets/${ticketId}`, ticketResponseSchema, {
    method: 'PATCH',
    body: JSON.stringify(update),
  })
}

export function unassignTicket(ticketId: string, expectedVersion: number) {
  return request(`/api/tickets/${ticketId}/unassign`, ticketResponseSchema, {
    method: 'POST',
    body: JSON.stringify({ expectedVersion }),
  })
}

export function reviewAnalysisReply(ticketId: string, analysisId: string, replyContent: string) {
  return request(`/api/tickets/${ticketId}/analyses/${analysisId}/reviews`, analysisReviewSchema, {
    method: 'POST',
    body: JSON.stringify({ replyContent }),
  })
}
