import { afterEach, expect, it, vi } from 'vitest'

import {
  analysisResponsePayload,
  metricsResponsePayload,
  nullableMetricsResponsePayload,
  ticketResponsePayload,
} from '../test/apiFixtures'
import { analyzeTicket, fetchMetrics, fetchTickets } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('rejects an analysis response when a required field is missing', async () => {
  // Given: Java 返回缺少 fallbackReason 的 2xx JSON。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...analysisResponsePayload('analysis-missing-field'),
        fallbackReason: undefined,
      }),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 分析响应跨过浏览器 HTTP 边界。
  const analysisRequest = analyzeTicket('ticket-missing-field')

  // Then: 坏数据必须在进入 React 状态前被类型化契约错误拒绝。
  await expect(analysisRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    path: '/api/tickets/ticket-missing-field/analyze',
    issues: [{ path: 'fallbackReason' }],
  })
})

it('rejects an analysis response when the mode is outside the contract', async () => {
  // Given: Java 返回 TypeScript 类型中不存在的新模式。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...analysisResponsePayload('analysis-invalid-mode'),
        mode: 'preview',
      }),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 前端读取分析响应。
  const analysisRequest = analyzeTicket('ticket-invalid-mode')

  // Then: 枚举漂移不能静默进入页面。
  await expect(analysisRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    issues: [{ path: 'mode' }],
  })
})

it('rejects an analysis response when an unknown field appears', async () => {
  // Given: Java 在未协调前端的情况下增加了响应字段。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...analysisResponsePayload('analysis-unknown-field'),
        internalDebugValue: 'must-not-cross-the-boundary',
      }),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 前端读取严格分析 Schema。
  const analysisRequest = analyzeTicket('ticket-unknown-field')

  // Then: 未知字段必须触发协调发布，而不是被静默丢弃。
  await expect(analysisRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    issues: [{ path: '$', code: 'unrecognized_keys' }],
  })
})

it('rejects fallback mode without a controlled fallback reason', async () => {
  // Given: 状态和模式表示降级，但原因字段为空。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...analysisResponsePayload('analysis-fallback-without-reason'),
        status: 'FALLBACK',
        mode: 'fallback',
        fallbackReason: null,
      }),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 降级响应进入浏览器边界。
  const analysisRequest = analyzeTicket('ticket-fallback-without-reason')

  // Then: 机器可读降级原因不能缺失。
  await expect(analysisRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    issues: [{ path: 'fallbackReason', code: 'custom' }],
  })
})

it('accepts fallback mode with a controlled fallback reason', async () => {
  // Given: Java 返回完整且可解释的降级组合。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...analysisResponsePayload('analysis-valid-fallback'),
        status: 'FALLBACK',
        mode: 'fallback',
        fallbackReason: 'ai_service_unavailable',
      }),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 前端读取降级响应。
  const analysisRequest = analyzeTicket('ticket-valid-fallback')

  // Then: 合法原因保留给页面和后续诊断。
  await expect(analysisRequest).resolves.toMatchObject({
    mode: 'fallback',
    status: 'FALLBACK',
    fallbackReason: 'ai_service_unavailable',
  })
})

it('rejects a ticket response when the server version is missing', async () => {
  // Given: 工单列表缺少真实命令所需的 version。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify([
        {
          ...ticketResponsePayload,
          version: undefined,
        },
      ]),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 浏览器加载工单列表。
  const ticketsRequest = fetchTickets()

  // Then: 不能把缺少并发控制版本的真实工单误当成演示工单。
  await expect(ticketsRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    issues: [{ path: '0.version' }],
  })
})

it('rejects metrics when a count is returned as text', async () => {
  // Given: 指标接口把数字字段错误序列化为字符串。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...metricsResponsePayload,
        summary: {
          ...metricsResponsePayload.summary,
          openTickets: '6',
        },
      }),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 浏览器加载指标。
  const metricsRequest = fetchMetrics()

  // Then: 前端不执行隐式数字转换。
  await expect(metricsRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    issues: [{ path: 'summary.openTickets' }],
  })
})

it('accepts nullable metrics when the backend has no report source', async () => {
  // Given: Java 返回真实快照，但没有耗时、采纳率和离线评估报告来源。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(nullableMetricsResponsePayload), { status: 200 }),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 浏览器读取当前可用指标。
  const metricsRequest = fetchMetrics()

  // Then: 可空字段保持 null，由页面显示“暂无来源”，而不是被转换成 0。
  await expect(metricsRequest).resolves.toMatchObject({
    summary: { analysisSuccessRate: null },
    analysisLatency: null,
    suggestionAcceptanceRate: null,
    evaluation: null,
  })
})

it('accepts traceable evaluation report metadata and measured fields', async () => {
  // Given: Java 返回固定评估报告中的来源和实际测量字段。
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(metricsResponsePayload), { status: 200 }),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: 浏览器读取质量指标。
  const metricsRequest = fetchMetrics()

  // Then: 页面可以展示报告来源、检索窗口和门禁结果。
  await expect(metricsRequest).resolves.toMatchObject({
    evaluation: {
      datasetName: 'tickets.jsonl',
      totalCases: 31,
      topN: 10,
      topK: 3,
      noEvidenceSafetyRate: 1,
      thresholdFailureCount: 0,
      passed: true,
    },
  })
})

it('rejects a successful response when its body is not JSON', async () => {
  // Given: HTTP 状态成功，但响应体不是 JSON。
  const fetchMock = vi.fn().mockResolvedValue(new Response('not-json', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  // When: 浏览器读取分析响应。
  const analysisRequest = analyzeTicket('ticket-invalid-json')

  // Then: JSON 解析失败也归入明确的响应契约错误。
  await expect(analysisRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    issues: [{ path: '$', code: 'invalid_json' }],
  })
  await expect(analysisRequest).rejects.not.toHaveProperty('cause')
})
