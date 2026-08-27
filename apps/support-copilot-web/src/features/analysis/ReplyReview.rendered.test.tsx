// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { analysisResultSchema, ticketResponseSchema } from '../../services/apiSchemas'
import { analysisResponsePayload, analysisReviewPayload, ticketResponsePayload } from '../../test/apiFixtures'
import { ReplyReview } from './ReplyReview'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderedReview() {
  class TestResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  const analysis = analysisResultSchema.parse({ ...analysisResponsePayload('analysis-1'), mode: 'live', modelName: 'secured-model' })
  const ticket = ticketResponseSchema.parse({ ...ticketResponsePayload, latestAnalysis: analysis, version: 4 })
  const onReviewSaved = vi.fn()
  const onToast = vi.fn()
  render(<ReplyReview ticket={ticket} analysis={analysis} onReviewSaved={onReviewSaved} onToast={onToast} />)
  return { analysis, onReviewSaved }
}

it('records approval of the unchanged suggestion', async () => {
  const approved = {
    ...analysisReviewPayload('review-approved'),
    action: 'APPROVED',
    reviewerType: 'AUTHENTICATED_JWT',
    reviewerLabel: 'reviewer-42',
    reviewedReplyContent: '我们会先核验交易记录。[1]',
  }
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(approved)))
  vi.stubGlobal('fetch', fetchMock)
  const { onReviewSaved } = renderedReview()

  fireEvent.click(screen.getByRole('button', { name: /记录审核/ }))
  expect(await screen.findByText('原建议已采纳 · reviewer-42')).toBeTruthy()
  expect(onReviewSaved).toHaveBeenCalledWith(expect.objectContaining({ action: 'APPROVED' }))
  expect(fetchMock).toHaveBeenCalledWith('/api/tickets/ticket-10042/analyses/analysis-1/reviews', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ replyContent: '我们会先核验交易记录。[1]' }),
  }))
})

it('records an edited suggestion', async () => {
  const editedContent = '我们会核验交易记录并同步进展。[1]'
  const edited = {
    ...analysisReviewPayload('review-edited'),
    reviewerType: 'AUTHENTICATED_JWT',
    reviewerLabel: 'reviewer-42',
    reviewedReplyContent: editedContent,
  }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(edited))))
  renderedReview()

  fireEvent.change(screen.getByLabelText('建议回复'), { target: { value: editedContent } })
  fireEvent.click(screen.getByRole('button', { name: /记录审核/ }))
  expect(await screen.findByText('编辑后已采纳 · reviewer-42')).toBeTruthy()
})

it('requires and records a rejection reason', async () => {
  const rejected = {
    ...analysisReviewPayload('review-rejected'),
    action: 'REJECTED',
    reviewerType: 'AUTHENTICATED_JWT',
    reviewerLabel: 'reviewer-42',
    reviewedReplyContent: null,
    reason: '证据不足',
  }
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(rejected)))
  vi.stubGlobal('fetch', fetchMock)
  const { onReviewSaved } = renderedReview()

  fireEvent.click(screen.getByRole('button', { name: /拒绝建议/ }))
  expect(screen.getByRole('button', { name: /确认拒绝/ }).hasAttribute('disabled')).toBe(true)
  fireEvent.change(screen.getByLabelText('拒绝原因'), { target: { value: '证据不足' } })
  fireEvent.click(screen.getByRole('button', { name: /确认拒绝/ }))
  await waitFor(() => expect(onReviewSaved).toHaveBeenCalledWith(expect.objectContaining({ action: 'REJECTED', reason: '证据不足' })))
  expect(fetchMock).toHaveBeenCalledWith('/api/tickets/ticket-10042/analyses/analysis-1/reviews/reject', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ reason: '证据不足' }),
  }))
})
