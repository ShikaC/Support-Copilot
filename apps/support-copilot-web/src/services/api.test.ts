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
