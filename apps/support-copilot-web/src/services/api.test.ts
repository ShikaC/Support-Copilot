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
