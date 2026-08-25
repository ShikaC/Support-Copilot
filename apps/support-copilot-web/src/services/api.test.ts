import { afterEach, expect, it, vi } from 'vitest'

import { analyzeTicket } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('posts the selected ticket id to the analysis endpoint', async () => {
  // Given: 浏览器会收到一份可解析的模拟成功响应。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 前端请求分析指定工单。
  await analyzeTicket('ticket-10042')

  // Then: 请求必须携带同一个工单编号，并使用 POST 方法。
  expect(fetchMock).toHaveBeenCalledOnce()
  expect(fetchMock).toHaveBeenCalledWith('/api/tickets/ticket-10042/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
})

it('shares one request while the same ticket analysis is in flight', async () => {
  // Given: the first request remains pending while a duplicate call arrives.
  let resolveResponse: ((response: Response) => void) | undefined
  const pendingResponse = new Promise<Response>((resolve) => {
    resolveResponse = resolve
  })
  const fetchMock = vi.fn().mockReturnValue(pendingResponse)
  vi.stubGlobal('fetch', fetchMock)

  // When: the browser requests the same ticket twice before the first response returns.
  const first = analyzeTicket('ticket-10042')
  const second = analyzeTicket('ticket-10042')
  resolveResponse?.(
    new Response('{"id":"analysis-shared"}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )

  // Then: both callers share one HTTP request and receive the same analysis.
  await expect(first).resolves.toEqual({ id: 'analysis-shared' })
  await expect(second).resolves.toEqual({ id: 'analysis-shared' })
  expect(fetchMock).toHaveBeenCalledOnce()
})

it('allows a new analysis request after the previous request settles', async () => {
  // Given: two sequential requests both return successfully.
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response('{"id":"analysis-first"}', { status: 200 }))
    .mockResolvedValueOnce(new Response('{"id":"analysis-retry"}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  // When: the user retries after the first request has completed.
  const first = await analyzeTicket('ticket-10042')
  const retry = await analyzeTicket('ticket-10042')

  // Then: in-flight sharing does not become a permanent response cache.
  expect(first).toEqual({ id: 'analysis-first' })
  expect(retry).toEqual({ id: 'analysis-retry' })
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('allows retry after the shared request fails', async () => {
  // Given: the first in-flight request fails before a later retry succeeds.
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new TypeError('simulated network failure'))
    .mockResolvedValueOnce(new Response('{"id":"analysis-after-failure"}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  // When: the user retries the same ticket after the failure is observed.
  await expect(analyzeTicket('ticket-10042')).rejects.toThrow('simulated network failure')
  const retry = await analyzeTicket('ticket-10042')

  // Then: the failed Promise was removed and a new HTTP request was sent.
  expect(retry).toEqual({ id: 'analysis-after-failure' })
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('does not block another ticket while one analysis remains in flight', async () => {
  // Given: one ticket request remains pending.
  let resolveFirst: ((response: Response) => void) | undefined
  const firstResponse = new Promise<Response>((resolve) => {
    resolveFirst = resolve
  })
  const fetchMock = vi.fn((path: string) =>
    path.includes('ticket-10042')
      ? firstResponse
      : Promise.resolve(new Response('{"id":"analysis-second-ticket"}', { status: 200 })),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: another ticket starts before the first one finishes.
  const first = analyzeTicket('ticket-10042')
  const second = analyzeTicket('ticket-10041')

  // Then: the second ticket completes independently.
  await expect(second).resolves.toEqual({ id: 'analysis-second-ticket' })
  resolveFirst?.(new Response('{"id":"analysis-first-ticket"}', { status: 200 }))
  await expect(first).resolves.toEqual({ id: 'analysis-first-ticket' })
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('preserves structured conflict details from the API', async () => {
  // Given: Java 返回带业务代码和版本信息的 409 响应。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        code: 'TICKET_VERSION_CONFLICT',
        message: '工单版本已变化',
        traceId: 'trace-409',
        details: { expectedVersion: 3, currentVersion: 4 },
      }),
      {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 前端请求分析已经发生版本冲突的工单。
  const analysisRequest = analyzeTicket('ticket-10042')

  // Then: React 收到的错误必须保留 Java 提供的结构化字段。
  await expect(analysisRequest).rejects.toMatchObject({
    name: 'ApiError',
    status: 409,
    code: 'TICKET_VERSION_CONFLICT',
    message: '工单版本已变化',
    traceId: 'trace-409',
    details: { expectedVersion: 3, currentVersion: 4 },
  })
})

it('uses default fields when an API error body is not JSON', async () => {
  // Given: Java 返回没有结构化 JSON 的 500 响应。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response('upstream unavailable', {
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 前端请求分析时收到无法解析的错误体。
  const analysisRequest = analyzeTicket('ticket-10042')

  // Then: React 使用 HTTP 状态生成稳定的默认错误字段。
  await expect(analysisRequest).rejects.toMatchObject({
    name: 'ApiError',
    status: 500,
    code: 'HTTP_500',
    message: 'API request failed: 500',
    traceId: null,
    details: {},
  })
})
