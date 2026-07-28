import type { AnalysisResult, Metrics, Ticket } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`)
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
