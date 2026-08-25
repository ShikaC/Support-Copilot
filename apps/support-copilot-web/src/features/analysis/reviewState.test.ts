import { describe, expect, it } from 'vitest'

import { analysisReviewPayload, ticketResponsePayload } from '../../test/apiFixtures'
import { analysisReviewSchema, ticketResponseSchema } from '../../services/apiSchemas'
import { applyAnalysisReview } from './reviewState'

describe('applyAnalysisReview', () => {
  it('keeps the saved review and timeline event in parent ticket state', () => {
    const ticket = ticketResponseSchema.parse(ticketResponsePayload)
    const review = analysisReviewSchema.parse({
      ...analysisReviewPayload('review-edited'),
      ticketId: ticket.id,
      analysisId: ticket.latestAnalysis?.id ?? 'analysis-1',
      action: 'EDITED',
      reviewedReplyContent: '人工修改后的回复',
    })

    const updated = applyAnalysisReview(ticket, review)

    expect(updated.latestReview).toEqual(review)
    expect(updated.events.at(-1)).toMatchObject({
      id: review.id,
      label: '人工审核已记录',
      detail: '未认证演示用户已编辑并采纳回复建议',
    })
  })

  it('replaces the previous review event instead of duplicating it', () => {
    const ticket = ticketResponseSchema.parse(ticketResponsePayload)
    const first = analysisReviewSchema.parse({
      ...analysisReviewPayload('review-first'),
      ticketId: ticket.id,
    })
    const second = analysisReviewSchema.parse({
      ...analysisReviewPayload('review-second'),
      ticketId: ticket.id,
      action: 'EDITED',
      reviewedReplyContent: '更新后的回复',
    })

    const updated = applyAnalysisReview(applyAnalysisReview(ticket, first), second)

    expect(updated.events.filter((event) => event.id.startsWith('review-'))).toHaveLength(1)
    expect(updated.latestReview?.id).toBe('review-second')
  })
})
