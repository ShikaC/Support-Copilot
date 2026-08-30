// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { analysisResponsePayload, metricsResponsePayload, ticketResponsePayload } from './test/apiFixtures'

vi.mock('echarts-for-react', () => ({ default: () => null }))

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

afterEach(() => {
  cleanup()
  window.sessionStorage.clear()
  vi.unstubAllGlobals()
})

function secondTicket() {
  return {
    ...ticketResponsePayload,
    id: 'ticket-20001',
    ticketNo: 'SC-20001',
    subject: '第二张工单',
    description: '需要人工复核的新问题。',
    version: 1,
  }
}

it('keeps ticket analyses independent and ignores a late response after switching', async () => {
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  let resolveFirst = (_response: Response) => {}
  const firstResponse = new Promise<Response>((resolve) => { resolveFirst = resolve })
  const fallback = {
    ...analysisResponsePayload('analysis-second'),
    traceId: 'trace-second-fallback',
    status: 'FALLBACK',
    mode: 'fallback',
    fallbackReason: 'insufficient_evidence',
    classification: { ...analysisResponsePayload('analysis-second').classification, reasonSummary: '第二张工单需要人工复核。' },
    retrieval: { query: '第二张工单', hits: [] },
  }
  const late = {
    ...analysisResponsePayload('analysis-first-late'),
    classification: { ...analysisResponsePayload('analysis-first-late').classification, reasonSummary: '旧工单迟到结果。' },
  }
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path === '/api/tickets' && init?.method === undefined) return Promise.resolve(new Response(JSON.stringify([ticketResponsePayload, secondTicket()])))
    if (path === '/api/metrics') return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload)))
    if (path === '/api/tickets/ticket-10042' && init?.method === undefined) return Promise.resolve(new Response(JSON.stringify({
      ...ticketResponsePayload,
      version: 1,
      status: 'NEEDS_ESCALATION',
      latestAnalysis: late,
    })))
    if (path === '/api/tickets/ticket-10042/analyze') return firstResponse
    if (path === '/api/tickets/ticket-20001' && init?.method === undefined) return Promise.resolve(new Response(JSON.stringify({
      ...secondTicket(),
      version: 2,
      status: 'NEEDS_ESCALATION',
      latestAnalysis: fallback,
    })))
    if (path === '/api/tickets/ticket-20001/analyze') return Promise.resolve(new Response(JSON.stringify(fallback)))
    return Promise.reject(new TypeError(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  window.sessionStorage.setItem('support-copilot.access-token', 'synthetic-analysis-token')
  render(<App authMode="secured" />)

  expect(await screen.findAllByText(ticketResponsePayload.subject)).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: '开始分析' }))
  expect(await screen.findByText('正在执行知识检索与风险检查')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /第二张工单/ }))
  fireEvent.click(screen.getByRole('button', { name: '开始分析' }))
  expect(await screen.findByText('第二张工单需要人工复核。')).toBeTruthy()
  fireEvent.click(screen.getByRole('tab', { name: /知识依据 0/ }))
  expect(await screen.findByText('没有找到充分证据')).toBeTruthy()

  await act(async () => { resolveFirst(new Response(JSON.stringify(late))); await firstResponse })
  expect(screen.getByText('第二张工单需要人工复核。')).toBeTruthy()
  expect(screen.queryByText('旧工单迟到结果。')).toBeNull()
})

it('leaves analysis controls usable after a transient failure and succeeds on retry', async () => {
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  let analysisAttempts = 0
  const retryAnalysis = analysisResponsePayload('analysis-retry-success')
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path === '/api/tickets' && init?.method === undefined) return Promise.resolve(new Response(JSON.stringify([ticketResponsePayload])))
    if (path === '/api/metrics') return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload)))
    if (path === '/api/tickets/ticket-10042/analyze') {
      analysisAttempts += 1
      return analysisAttempts === 1
        ? Promise.reject(new TypeError('transient'))
        : Promise.resolve(new Response(JSON.stringify(retryAnalysis)))
    }
    if (path === '/api/tickets/ticket-10042' && init?.method === undefined) return Promise.resolve(new Response(JSON.stringify({
      ...ticketResponsePayload,
      version: 1,
      status: 'NEEDS_ESCALATION',
      latestAnalysis: retryAnalysis,
    })))
    return Promise.reject(new TypeError(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  window.sessionStorage.setItem('support-copilot.access-token', 'synthetic-analysis-token')
  render(<App authMode="secured" />)

  fireEvent.click(await screen.findByRole('button', { name: '开始分析' }))
  expect((await screen.findByRole('alert')).textContent).toContain('无法连接业务服务')
  fireEvent.click(await screen.findByRole('button', { name: '开始分析' }))
  expect(await screen.findByText('账单重复扣款需要人工核验。')).toBeTruthy()
  await waitFor(() => expect(analysisAttempts).toBe(2))
  const keys = fetchMock.mock.calls
    .filter(([input]) => input === '/api/tickets/ticket-10042/analyze')
    .map(([, init]) => new Headers(init?.headers).get('Idempotency-Key'))
  expect(keys[0]).toBeTruthy()
  expect(keys[1]).toBe(keys[0])
})

it('refreshes server-owned ticket fields and version after analysis', async () => {
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  const initialTicket = { ...ticketResponsePayload, category: 'UNCLASSIFIED', priority: 'MEDIUM', version: 4 }
  const analysis = analysisResponsePayload('analysis-refreshes-ticket')
  const updatedTicket = {
    ...initialTicket,
    category: 'BILLING',
    priority: 'HIGH',
    status: 'READY_FOR_REVIEW',
    version: 5,
    updatedAt: '2026-08-25T02:30:00Z',
    latestAnalysis: analysis,
  }
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path === '/api/tickets' && init?.method === undefined) return Promise.resolve(new Response(JSON.stringify([initialTicket])))
    if (path === '/api/metrics') return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload)))
    if (path === '/api/tickets/ticket-10042/analyze') return Promise.resolve(new Response(JSON.stringify(analysis)))
    if (path === '/api/tickets/ticket-10042' && init?.method === undefined) return Promise.resolve(new Response(JSON.stringify(updatedTicket)))
    if (path === '/api/tickets/ticket-10042' && init?.method === 'PATCH') return Promise.resolve(new Response(JSON.stringify({
      ...updatedTicket,
      assigneeName: '演示管理员',
      version: 6,
    })))
    return Promise.reject(new TypeError(`Unexpected request: ${path}:${init?.method ?? 'GET'}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  window.sessionStorage.setItem('support-copilot.access-token', 'synthetic-analysis-token')
  render(<App authMode="secured" />)

  fireEvent.click(await screen.findByRole('button', { name: '开始分析' }))
  expect(await screen.findAllByText('账单支付')).toHaveLength(2)
  fireEvent.click(await screen.findByRole('button', { name: '领取工单' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/tickets/ticket-10042', expect.objectContaining({
    method: 'PATCH',
    body: JSON.stringify({ assigneeName: '演示管理员', expectedVersion: 5 }),
  })))
})
