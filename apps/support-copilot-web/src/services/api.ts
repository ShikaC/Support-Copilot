import * as z from 'zod'

import { configuredAuthMode, createAuthSession, type AuthSession } from '../auth/authSession'
import type { AnalysisResult, PersistedTicketStatus, Ticket } from '../types'
import {
  analysisReviewListSchema,
  analysisReviewSchema,
  analysisResultSchema,
  auditEventPageSchema,
  knowledgeHitListSchema,
  knowledgeReleaseListSchema,
  knowledgeReleaseSchema,
  metricsResponseSchema,
  ticketResponseListSchema,
  ticketResponseSchema,
} from './apiSchemas'

const apiErrorSchema = z.union([
  z.strictObject({ code: z.string().min(1), message: z.string().min(1), traceId: z.string().min(1) }),
  z.strictObject({
    code: z.string().min(1),
    message: z.string().min(1),
    traceId: z.string().min(1),
    timestamp: z.iso.datetime({ offset: true }),
    details: z.record(z.string(), z.unknown()),
  }),
])

export class ApiError extends Error {
  readonly name = 'ApiError'
  readonly status: number
  readonly code: string
  readonly traceId: string
  readonly details: Readonly<Record<string, unknown>>
  constructor(
    status: number,
    code: string,
    message: string,
    traceId: string,
    details: Readonly<Record<string, unknown>>,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.traceId = traceId
    this.details = details
  }
}

export type ApiContractIssue = { readonly path: string; readonly code: string }

export class ApiContractError extends Error {
  readonly name = 'ApiContractError'
  readonly path: string
  readonly issues: readonly ApiContractIssue[]
  constructor(path: string, issues: readonly ApiContractIssue[]) {
    super(`API response contract mismatch for ${path}`)
    this.path = path
    this.issues = issues
  }
}

export type ApiRequestErrorKind = 'network' | 'timeout' | 'cancelled'

export class ApiRequestError extends Error {
  readonly name = 'ApiRequestError'
  readonly kind: ApiRequestErrorKind
  constructor(kind: ApiRequestErrorKind) {
    super(kind === 'timeout' ? '请求超时，请重试' : kind === 'cancelled' ? '请求已取消' : '无法连接业务服务')
    this.kind = kind
  }
}

type RequestOptions = { readonly signal?: AbortSignal }
type ClientOptions = { readonly auth: AuthSession; readonly baseUrl: string; readonly timeoutMs: number }
type TicketUpdate = Partial<Pick<Ticket, 'priority' | 'category' | 'assigneeName'>> & {
  readonly status?: PersistedTicketStatus
}
export type ReleaseAction = 'approve' | 'publish' | 'rollback'

function contractIssues(error: z.ZodError): readonly ApiContractIssue[] {
  return error.issues.map((issue) => ({
    path: issue.path.length === 0 ? '$' : issue.path.join('.'),
    code: issue.code,
  }))
}

function requestSignal(timeoutMs: number, signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(timeoutMs)
  return signal === undefined ? timeout : AbortSignal.any([signal, timeout])
}

function classifyRequestError(error: unknown, signal?: AbortSignal): ApiRequestError | null {
  if (signal?.aborted) return new ApiRequestError('cancelled')
  if (error instanceof DOMException && error.name === 'TimeoutError') return new ApiRequestError('timeout')
  if (error instanceof DOMException && error.name === 'AbortError') return new ApiRequestError('cancelled')
  return error instanceof TypeError ? new ApiRequestError('network') : null
}

export function createApiClient(options: ClientOptions) {
  const uncertainKeys = new Map<string, string>()
  const inFlightAnalyses = new Map<string, Promise<AnalysisResult>>()

  async function request<Schema extends z.ZodType>(
    path: string,
    schema: Schema,
    init: RequestInit = {},
  ): Promise<z.output<Schema>> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = options.auth.accessToken()
    if (token !== null) headers.Authorization = `Bearer ${token}`
    if (init.headers !== undefined) {
      new Headers(init.headers).forEach((value, key) => {
        headers[key === 'idempotency-key' ? 'Idempotency-Key' : key] = value
      })
    }
    const callerSignal = init.signal ?? undefined
    let response: Response
    try {
      response = await fetch(`${options.baseUrl}${path}`, {
        ...init,
        headers,
        signal: requestSignal(options.timeoutMs, callerSignal),
      })
    } catch (error: unknown) {
      const classified = classifyRequestError(error, callerSignal)
      if (classified !== null) throw classified
      throw error
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
    if (!response.ok) {
      const parsedError = apiErrorSchema.safeParse(payload)
      if (!parsedError.success) throw new ApiContractError(path, contractIssues(parsedError.error))
      throw new ApiError(
        response.status,
        parsedError.data.code,
        parsedError.data.message,
        parsedError.data.traceId,
        'details' in parsedError.data ? parsedError.data.details : {},
      )
    }
    const parsed = schema.safeParse(payload)
    if (!parsed.success) throw new ApiContractError(path, contractIssues(parsed.error))
    return parsed.data
  }

  async function command<Schema extends z.ZodType>(
    fingerprint: string,
    path: string,
    schema: Schema,
    init: RequestInit,
  ): Promise<z.output<Schema>> {
    const key = uncertainKeys.get(fingerprint) ?? crypto.randomUUID()
    uncertainKeys.set(fingerprint, key)
    const result = await request(path, schema, {
      ...init,
      headers: { ...init.headers, 'Idempotency-Key': key },
    })
    uncertainKeys.delete(fingerprint)
    return result
  }

  return {
    fetchTickets: (requestOptions: RequestOptions = {}) =>
      request('/api/tickets', ticketResponseListSchema, { signal: requestOptions.signal }),
    fetchTicket: (ticketId: string, requestOptions: RequestOptions = {}) =>
      request(`/api/tickets/${ticketId}`, ticketResponseSchema, { signal: requestOptions.signal }),
    fetchMetrics: (requestOptions: RequestOptions = {}) =>
      request('/api/metrics', metricsResponseSchema, { signal: requestOptions.signal }),
    analyzeTicket(ticketId: string, requestOptions: RequestOptions = {}) {
      const existing = inFlightAnalyses.get(ticketId)
      if (existing !== undefined) return existing
      const pending = command(
        `ANALYZE:${ticketId}`,
        `/api/tickets/${ticketId}/analyze`,
        analysisResultSchema,
        { method: 'POST', signal: requestOptions.signal },
      )
      const tracked = pending.finally(() => {
        if (inFlightAnalyses.get(ticketId) === tracked) inFlightAnalyses.delete(ticketId)
      })
      inFlightAnalyses.set(ticketId, tracked)
      return tracked
    },
    updateTicket: (ticketId: string, update: TicketUpdate, expectedVersion: number) =>
      request(`/api/tickets/${ticketId}`, ticketResponseSchema, {
        method: 'PATCH', body: JSON.stringify({ ...update, expectedVersion }),
      }),
    unassignTicket: (ticketId: string, expectedVersion: number) =>
      request(`/api/tickets/${ticketId}/unassign`, ticketResponseSchema, {
        method: 'POST', body: JSON.stringify({ expectedVersion }),
      }),
    reviewAnalysisReply: (ticketId: string, analysisId: string, replyContent: string) =>
      command(
        `REVIEW:${ticketId}:${analysisId}:${JSON.stringify(replyContent.trim())}`,
        `/api/tickets/${ticketId}/analyses/${analysisId}/reviews`,
        analysisReviewSchema,
        { method: 'POST', body: JSON.stringify({ replyContent }) },
      ),
    rejectAnalysisReply: (ticketId: string, analysisId: string, reason: string) =>
      command(
        `REJECT:${ticketId}:${analysisId}:${JSON.stringify(reason.trim())}`,
        `/api/tickets/${ticketId}/analyses/${analysisId}/reviews/reject`,
        analysisReviewSchema,
        { method: 'POST', body: JSON.stringify({ reason }) },
      ),
    fetchAnalysisReviews: (ticketId: string, analysisId: string) =>
      request(`/api/tickets/${ticketId}/analyses/${analysisId}/reviews`, analysisReviewListSchema),
    searchKnowledge: (query: string, topK = 10) =>
      request(`/api/knowledge/search?${new URLSearchParams({ query, topK: String(topK) })}`, knowledgeHitListSchema),
    fetchKnowledgeReleases: () => request('/api/knowledge/releases', knowledgeReleaseListSchema),
    transitionKnowledgeRelease: (releaseId: string, action: ReleaseAction, expectedVersion: number) =>
      request(`/api/knowledge/releases/${releaseId}/${action}`, knowledgeReleaseSchema, {
        method: 'POST', body: JSON.stringify({ expectedVersion }),
      }),
    fetchAuditEvents: (cursor?: string) => {
      const query = cursor === undefined ? '' : `?${new URLSearchParams({ cursor, limit: '20' })}`
      return request(`/api/audit-events${query}`, auditEventPageSchema)
    },
  }
}

export type ApiClient = ReturnType<typeof createApiClient>

const defaultClient = createApiClient({
  auth: createAuthSession({ mode: configuredAuthMode() }),
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '',
  timeoutMs: 8000,
})

export const fetchTickets = (signal?: AbortSignal) => defaultClient.fetchTickets({ signal })
export const fetchTicket = (ticketId: string, signal?: AbortSignal) => defaultClient.fetchTicket(ticketId, { signal })
export const fetchMetrics = (signal?: AbortSignal) => defaultClient.fetchMetrics({ signal })
export const analyzeTicket = (ticketId: string) => defaultClient.analyzeTicket(ticketId)
export const updateTicket = (ticketId: string, update: TicketUpdate, version: number) => defaultClient.updateTicket(ticketId, update, version)
export const unassignTicket = (ticketId: string, version: number) => defaultClient.unassignTicket(ticketId, version)
export const reviewAnalysisReply = (ticketId: string, analysisId: string, content: string) => defaultClient.reviewAnalysisReply(ticketId, analysisId, content)
export const rejectAnalysisReply = (ticketId: string, analysisId: string, reason: string) => defaultClient.rejectAnalysisReply(ticketId, analysisId, reason)
export const fetchAnalysisReviews = (ticketId: string, analysisId: string) => defaultClient.fetchAnalysisReviews(ticketId, analysisId)
