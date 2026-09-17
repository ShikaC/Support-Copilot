// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../../auth/authSession'
import { createApiClient } from '../../services/api'
import { analysisResultSchema, ticketResponseSchema } from '../../services/apiSchemas'
import { analysisResponsePayload, ticketResponsePayload } from '../../test/apiFixtures'
import { AnalysisColumn } from './AnalysisColumn'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it.each([
  { state: 'no candidates', adopted: [], count: 0 },
  { state: 'only unadopted candidates', adopted: [false, false], count: 0 },
  { state: 'mixed candidates', adopted: [true, false], count: 1 },
])('separates reply evidence from retrieval candidates: $state', ({ adopted, count }) => {
  class TestResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  const payload = analysisResponsePayload('analysis-evidence')
  const originalHit = payload.retrieval.hits[0]
  if (!originalHit) throw new TypeError('Fixture requires a knowledge hit')
  const analysis = analysisResultSchema.parse({
    ...payload,
    retrieval: {
      query: '合成证据测试',
      hits: adopted.map((usedAsEvidence, index) => ({
        ...originalHit,
        chunkId: `chunk-${index}`,
        documentTitle: `候选文档 ${index + 1}`,
        rerankPosition: index + 1,
        usedAsEvidence,
      })),
    },
  })
  const ticket = ticketResponseSchema.parse({ ...ticketResponsePayload, latestAnalysis: analysis })
  const client = createApiClient({ auth: createAuthSession({ mode: 'demo' }), baseUrl: '', timeoutMs: 1000 })
  render(<AnalysisColumn ticket={ticket} client={client} analyzing={false} onAnalyze={vi.fn()} onReviewSaved={vi.fn()} onRefreshTicket={vi.fn()} onToast={vi.fn()} />)

  fireEvent.click(screen.getByRole('tab', { name: `知识依据 ${count}` }))
  expect(screen.queryByText('没有找到充分证据') !== null).toBe(count === 0)
  expect(screen.queryByText('当前没有可作为回复依据的知识，需要人工复核。') !== null).toBe(count === 0)
  expect(screen.queryByText('未进入上下文')).toBeNull()
  for (const [index, usedAsEvidence] of adopted.entries()) {
    const candidate = screen.getByRole('button', { name: new RegExp(`候选文档 ${index + 1}`) })
    expect(candidate.textContent).toContain(usedAsEvidence ? '已作为回复依据' : '未作为回复依据')
    const expanded = candidate.getAttribute('aria-expanded') === 'true'
    fireEvent.click(candidate)
    expect(candidate.getAttribute('aria-expanded')).toBe(String(!expanded))
    fireEvent.click(candidate)
    expect(candidate.getAttribute('aria-expanded')).toBe(String(expanded))
  }
})
