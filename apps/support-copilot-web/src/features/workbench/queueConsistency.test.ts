// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../../auth/authSession'
import { createApiClient } from '../../services/api'
import { analysisResponsePayload, metricsResponsePayload, ticketResponsePayload } from '../../test/apiFixtures'
import { useTicketWorkflow } from './useTicketWorkflow'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('filters pending tickets on the first server page and preserves a successful edit against a late queue response', async () => {
  const initial = { ...ticketResponsePayload, version: 1 }
  let releaseQueue: ((response: Response) => void) | undefined
  let queueCalls = 0
  const fetcher = vi.fn((input: string, init?: RequestInit) => {
    if (input.startsWith('/api/tickets?')) {
      queueCalls += 1
      if (queueCalls > 1) return new Promise<Response>((resolve) => { releaseQueue = resolve })
      return Promise.resolve(new Response(JSON.stringify([initial])))
    }
    if (input === '/api/metrics') return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload)))
    if (init?.method === 'PATCH') return Promise.resolve(new Response(JSON.stringify({ ...initial, version: 2, assigneeName: '已保存的负责人' })))
    throw new Error('Unexpected request: ' + input)
  })
  vi.stubGlobal('fetch', fetcher)
  const auth = createAuthSession({ mode: 'demo' })
  const client = createApiClient({ auth, baseUrl: '', timeoutMs: 8000 })
  const { result } = renderHook(() => useTicketWorkflow({ auth, client }))
  await waitFor(() => expect(result.current.selectedTicket?.version).toBe(1))
  const firstUrl = new URL(fetcher.mock.calls[0]?.[0] ?? '', 'https://example.test')
  expect(firstUrl.searchParams.get('status')?.split(',')).toContain('IN_PROGRESS')
  expect(firstUrl.searchParams.get('status')?.split(',')).not.toContain('CLOSED')
  act(() => result.current.refresh())
  await waitFor(() => expect(releaseQueue).toBeDefined())
  await act(async () => { await result.current.updateSelectedTicket({ assigneeName: '已保存的负责人' }) })
  await act(async () => { releaseQueue?.(new Response(JSON.stringify([initial]))) })
  expect(result.current.selectedTicket?.version).toBe(2)
  expect(result.current.selectedTicket?.assigneeName).toBe('已保存的负责人')
})

it('refreshes server membership and count after resolving a ticket while preserving its selected detail', async () => {
  let resolved = false
  const current = () => ({ ...ticketResponsePayload, version: resolved ? 2 : 1, status: resolved ? 'RESOLVED' : 'IN_PROGRESS' })
  const fetcher = vi.fn((input: string, init?: RequestInit) => {
    if (input.startsWith('/api/tickets?')) return Promise.resolve(new Response(JSON.stringify(resolved ? [] : [current()]), { headers: { 'X-Total-Count': resolved ? '0' : '1' } }))
    if (input === '/api/metrics') return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload)))
    if (init?.method === 'PATCH') { resolved = true; return Promise.resolve(new Response(JSON.stringify(current()))) }
    throw new Error('Unexpected request: ' + input)
  })
  vi.stubGlobal('fetch', fetcher)
  const auth = createAuthSession({ mode: 'demo' })
  const client = createApiClient({ auth, baseUrl: '', timeoutMs: 8000 })
  const { result } = renderHook(() => useTicketWorkflow({ auth, client }))
  await waitFor(() => expect(result.current.totalCount).toBe(1))
  await act(async () => { await result.current.updateSelectedTicket({ status: 'RESOLVED' }) })
  await waitFor(() => expect(result.current.totalCount).toBe(0))
  expect(result.current.queueTickets).toEqual([])
  expect(result.current.selectedTicket?.status).toBe('RESOLVED')
})


it('keeps a persisted analysis visible when its immediate detail refresh fails', async () => {
  let analyzed = false
  const analysis = analysisResponsePayload('analysis-persisted-refresh-failure')
  const current = () => ({ ...ticketResponsePayload, version: analyzed ? 2 : 1, latestAnalysis: analyzed ? analysis : null })
  const fetcher = vi.fn((input: string) => {
    if (input.startsWith('/api/tickets?')) return Promise.resolve(new Response(JSON.stringify([current()])))
    if (input === '/api/metrics') return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload)))
    if (input.endsWith('/analyze')) { analyzed = true; return Promise.resolve(new Response(JSON.stringify(analysis))) }
    if (input === '/api/tickets/' + ticketResponsePayload.id) return Promise.reject(new TypeError('detail refresh connection lost'))
    throw new Error('Unexpected request: ' + input)
  })
  vi.stubGlobal('fetch', fetcher)
  const auth = createAuthSession({ mode: 'demo' })
  const client = createApiClient({ auth, baseUrl: '', timeoutMs: 8000 })
  const { result } = renderHook(() => useTicketWorkflow({ auth, client }))
  await waitFor(() => expect(result.current.selectedTicket?.version).toBe(1))
  await act(async () => { await result.current.runAnalysis() })
  await waitFor(() => expect(result.current.selectedTicket?.latestAnalysis?.id).toBe(analysis.id))
  expect(result.current.toast?.message).toContain('分析已保存')
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/analyze'))).toHaveLength(1)
})

it('discards the old filtered page even if it resolves after a replacement query', async () => {
  let releaseOld: ((response: Response) => void) | undefined
  const fetcher = vi.fn((input: string) => {
    if (input.startsWith('/api/tickets?')) {
      if (input.includes('keyword=new')) return Promise.resolve(new Response(JSON.stringify([]), { headers: { 'X-Total-Count': '0' } }))
      return new Promise<Response>((resolve) => { releaseOld = resolve })
    }
    if (input === '/api/metrics') return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload)))
    throw new Error('Unexpected request: ' + input)
  })
  vi.stubGlobal('fetch', fetcher)
  const auth = createAuthSession({ mode: 'demo' })
  const client = createApiClient({ auth, baseUrl: '', timeoutMs: 8000 })
  const { result } = renderHook(() => useTicketWorkflow({ auth, client }))
  await waitFor(() => expect(releaseOld).toBeDefined())
  await act(async () => {
    result.current.setQueueQuery({ keyword: 'new' })
    releaseOld?.(new Response(JSON.stringify([ticketResponsePayload]), { headers: { 'X-Total-Count': '100' } }))
  })
  await waitFor(() => expect(result.current.totalCount).toBe(0))
  expect(result.current.queueTickets).toEqual([])
})
