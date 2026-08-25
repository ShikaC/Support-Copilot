import { afterEach, expect, it, vi } from 'vitest'

import { analysisReviewPayload } from '../test/apiFixtures'
import { reviewAnalysisReply } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('posts the reviewed reply to the explicit analysis review command', async () => {
  // Given: Java accepts an edited reply and returns the persisted review record.
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(analysisReviewPayload('review-1')), { status: 200 }),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: the browser records a human review for one analysis.
  const review = await reviewAnalysisReply('ticket-10042', 'analysis-1', '修改后的回复')

  // Then: the command path, content, and typed persisted result are preserved.
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/tickets/ticket-10042/analyses/analysis-1/reviews',
    {
      method: 'POST',
      body: JSON.stringify({ replyContent: '修改后的回复' }),
      headers: { 'Content-Type': 'application/json' },
    },
  )
  expect(review).toMatchObject({
    id: 'review-1',
    action: 'EDITED',
    reviewerType: 'UNAUTHENTICATED_DEMO',
  })
})

it('preserves a stale analysis review conflict', async () => {
  // Given: Java rejects a review after the ticket or latest analysis changed.
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        code: 'ANALYSIS_REVIEW_STALE',
        message: '工单或分析结果已经变化，请刷新后重新审核。',
        traceId: 'trace-review-conflict',
        details: { analysisId: 'analysis-old', latestAnalysisId: 'analysis-latest' },
      }),
      { status: 409 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: the browser submits the old analysis review.
  const reviewRequest = reviewAnalysisReply('ticket-10042', 'analysis-old', '回复')

  // Then: the page can distinguish a stale review from a generic network failure.
  await expect(reviewRequest).rejects.toMatchObject({
    name: 'ApiError',
    status: 409,
    code: 'ANALYSIS_REVIEW_STALE',
    traceId: 'trace-review-conflict',
  })
})

it('rejects an analysis review response with an unknown action', async () => {
  // Given: the server returns an action that the page does not understand.
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...analysisReviewPayload('review-invalid-action'),
        action: 'SENT',
      }),
      { status: 200 },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  // When: the response crosses the frontend runtime boundary.
  const reviewRequest = reviewAnalysisReply('ticket-10042', 'analysis-1', '回复')

  // Then: unsupported workflow states cannot silently enter the UI.
  await expect(reviewRequest).rejects.toMatchObject({
    name: 'ApiContractError',
    issues: [{ path: 'action' }],
  })
})
