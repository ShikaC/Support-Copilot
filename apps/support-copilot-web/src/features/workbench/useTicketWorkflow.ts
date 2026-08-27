import { useEffect, useRef, useState } from 'react'
import type { AuthSession } from '../../auth/authSession'
import { ApiError, ApiRequestError, type ApiClient } from '../../services/api'
import { createDemoAnalysis, demoTickets } from '../../data/demoData'
import type { AnalysisReview, Metrics, Ticket } from '../../types'
import { applyAnalysisReview } from '../analysis/reviewState'

export type ApiState = 'connecting' | 'connected' | 'partial' | 'demo' | 'unauthenticated' | 'unavailable'
export type ToastMessage = { readonly kind: 'success' | 'error'; readonly message: string }

type TicketWorkflowOptions = { readonly auth: AuthSession; readonly client: ApiClient }

export function useTicketWorkflow({ auth, client }: TicketWorkflowOptions) {
  const initialTickets = auth.mode === 'demo' ? demoTickets : []
  const [tickets, setTickets] = useState<Ticket[]>(initialTickets)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [metricsError, setMetricsError] = useState(false)
  const [selectedTicketId, setSelectedTicketId] = useState(initialTickets[0]?.id ?? '')
  const [apiState, setApiState] = useState<ApiState>('connecting')
  const [analyzingTicketIds, setAnalyzingTicketIds] = useState<readonly string[]>([])
  const [assigneeTicketIds, setAssigneeTicketIds] = useState<readonly string[]>([])
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const toastTimer = useRef<number | null>(null)
  const analysisControllers = useRef(new Map<string, AbortController>())
  const selectedTicket = tickets.find((ticket) => ticket.id === selectedTicketId) ?? tickets[0] ?? null

  useEffect(() => {
    const controller = new AbortController()
    Promise.allSettled([
      client.fetchTickets({ signal: controller.signal }),
      client.fetchMetrics({ signal: controller.signal }),
    ]).then(([ticketResult, metricResult]) => {
      if (controller.signal.aborted) return
      const ticketsAvailable = ticketResult.status === 'fulfilled'
      const metricsAvailable = metricResult.status === 'fulfilled'
      if (ticketsAvailable) {
        setTickets(ticketResult.value)
        setSelectedTicketId((current) => ticketResult.value.some((item) => item.id === current) ? current : ticketResult.value[0]?.id ?? '')
      } else if (auth.mode === 'secured') {
        setTickets([])
        if (ticketResult.reason instanceof ApiError && ticketResult.reason.status === 401) setApiState('unauthenticated')
      }
      if (metricsAvailable) {
        setMetrics(metricResult.value)
        setMetricsError(false)
      } else {
        setMetrics(null)
        setMetricsError(!(metricResult.reason instanceof ApiRequestError && metricResult.reason.kind === 'cancelled'))
      }
      if (ticketResult.status === 'rejected' && ticketResult.reason instanceof ApiError && ticketResult.reason.status === 401) return
      setApiState(ticketsAvailable && metricsAvailable
        ? 'connected'
        : ticketsAvailable || metricsAvailable
          ? 'partial'
          : auth.mode === 'demo' ? 'demo' : 'unavailable')
    })
    return () => controller.abort()
  }, [auth.mode, client])

  useEffect(() => () => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    analysisControllers.current.forEach((controller) => controller.abort())
  }, [])

  const showToast = (message: string, kind: 'success' | 'error' = 'success') => {
    setToast({ kind, message })
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 3200)
  }

  const reconcileTicket = async (ticketId: string) => {
    try {
      const latest = await client.fetchTicket(ticketId)
      setTickets((current) => current.map((ticket) => ticket.id === latest.id ? latest : ticket))
    } catch (error: unknown) {
      if (error instanceof ApiError || error instanceof ApiRequestError) return
      throw error
    }
  }

  const runAnalysis = async () => {
    if (selectedTicket === null || analyzingTicketIds.includes(selectedTicket.id)) return
    const requestTicket = selectedTicket
    const controller = new AbortController()
    analysisControllers.current.set(requestTicket.id, controller)
    setAnalyzingTicketIds((current) => [...current, requestTicket.id])
    setTickets((current) => current.map((ticket) => ticket.id === requestTicket.id ? { ...ticket, latestAnalysis: undefined, latestReview: undefined } : ticket))
    try {
      const result = await client.analyzeTicket(requestTicket.id, { signal: controller.signal })
      if (controller.signal.aborted) return
      setTickets((current) => current.map((ticket) => ticket.id === requestTicket.id ? {
        ...ticket,
        latestAnalysis: result,
        latestReview: null,
        status: result.decision.escalationRequired ? 'NEEDS_ESCALATION' : 'READY_FOR_REVIEW',
        updatedAt: new Date().toISOString(),
      } : ticket))
      setApiState((current) => current === 'connected' ? current : 'partial')
      showToast('分析完成，分类、证据和回复建议已更新')
    } catch (error: unknown) {
      if (error instanceof ApiRequestError && error.kind === 'cancelled') return
      if (error instanceof ApiError) {
        if (error.code === 'VERSION_CONFLICT') await reconcileTicket(requestTicket.id)
        const trace = error.traceId.length > 0 ? `（traceId: ${error.traceId}）` : ''
        showToast(error.code === 'VERSION_CONFLICT' ? `工单 ${requestTicket.id} 版本已变化，请重新加载后再分析${trace}` : error.message, 'error')
        return
      }
      if (error instanceof ApiRequestError && auth.mode === 'demo' && error.kind === 'network') {
        const result = createDemoAnalysis(requestTicket)
        setTickets((current) => current.map((ticket) => ticket.id === requestTicket.id ? { ...ticket, latestAnalysis: result, latestReview: null, status: result.decision.escalationRequired ? 'NEEDS_ESCALATION' : 'READY_FOR_REVIEW', updatedAt: new Date().toISOString() } : ticket))
        setApiState('demo')
        showToast('已使用演示分析结果，启动后端后可切换到服务模式')
        return
      }
      showToast(error instanceof ApiRequestError ? error.message : '分析失败，请稍后重试', 'error')
    } finally {
      analysisControllers.current.delete(requestTicket.id)
      setAnalyzingTicketIds((current) => current.filter((id) => id !== requestTicket.id))
    }
  }

  const updateAssignee = async (unassign: boolean) => {
    if (selectedTicket === null || assigneeTicketIds.includes(selectedTicket.id)) return
    const requestTicket = selectedTicket
    if (requestTicket.version === undefined) {
      setTickets((current) => current.map((ticket) => ticket.id === requestTicket.id ? { ...ticket, assigneeName: unassign ? null : '演示管理员', updatedAt: new Date().toISOString() } : ticket))
      showToast(unassign ? '已在演示数据中取消负责人' : '已在演示数据中更新负责人')
      return
    }
    setAssigneeTicketIds((current) => [...current, requestTicket.id])
    try {
      const updated = unassign
        ? await client.unassignTicket(requestTicket.id, requestTicket.version)
        : await client.updateTicket(requestTicket.id, { assigneeName: '演示管理员' }, requestTicket.version)
      setTickets((current) => current.map((ticket) => ticket.id === updated.id ? updated : ticket))
      showToast(unassign ? '负责人已取消' : '工单已分配给演示管理员')
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === 'VERSION_CONFLICT') await reconcileTicket(requestTicket.id)
      const fallback = unassign ? '服务不可用，负责人未取消' : '服务不可用，负责人未更新'
      const conflictMessage = unassign
        ? '工单已被其他操作更新，请刷新后再取消负责人'
        : '工单已被其他操作更新，请刷新后再更新负责人'
      showToast(error instanceof ApiError && error.code !== 'VERSION_CONFLICT' ? error.message : error instanceof ApiError ? conflictMessage : fallback, 'error')
    } finally {
      setAssigneeTicketIds((current) => current.filter((id) => id !== requestTicket.id))
    }
  }

  const recordReview = (review: AnalysisReview) => setTickets((current) => current.map((ticket) => applyAnalysisReview(ticket, review)))
  return {
    tickets, metrics, metricsError, selectedTicket, selectedTicketId, setSelectedTicketId,
    apiState, analyzingTicketIds, assigneeTicketIds, toast, showToast, runAnalysis,
    assignSelectedTicket: () => updateAssignee(false), unassignSelectedTicket: () => updateAssignee(true),
    recordReview, reconcileTicket,
  }
}
