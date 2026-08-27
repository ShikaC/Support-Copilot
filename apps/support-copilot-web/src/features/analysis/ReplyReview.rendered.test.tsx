// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../../auth/authSession'
import { createApiClient } from '../../services/api'
import { analysisResultSchema, ticketResponseSchema } from '../../services/apiSchemas'
import { analysisResponsePayload, analysisReviewPayload, ticketResponsePayload } from '../../test/apiFixtures'
import { ReplyReview } from './ReplyReview'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderedReview(options: {
  readonly client?: ReturnType<typeof createApiClient>
  readonly onRefreshTicket?: (ticketId: string) => Promise<void>
} = {}) {
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
  const client = options.client ?? createApiClient({
    auth: createAuthSession({ mode: 'demo' }), baseUrl: '', timeoutMs: 1000,
  })
  render(<ReplyReview ticket={ticket} analysis={analysis} client={client} onRefreshTicket={options.onRefreshTicket ?? vi.fn()} onReviewSaved={onReviewSaved} onToast={onToast} />)
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

it('uses the injected secured client and refreshes the stale ticket before showing retry', async () => {
  // Given: a secured application client and a review rejected because the persisted ticket moved.
  const auth = createAuthSession({ mode: 'secured' })
  auth.setAccessToken('review-stale-token')
  const client = createApiClient({ auth, baseUrl: '', timeoutMs: 1000 })
  const staleError = {
    code: 'ANALYSIS_REVIEW_STALE',
    message: '工单或分析结果已经变化，请刷新后重新审核。',
    traceId: 'trace-review-stale',
    timestamp: '2026-08-27T00:00:00Z',
    details: { analysisId: 'analysis-1', latestAnalysisId: 'analysis-2' },
  }
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path.endsWith('/reviews')) return Promise.resolve(new Response(JSON.stringify(staleError), { status: 409 }))
    if (path === '/api/tickets/ticket-10042') return Promise.resolve(new Response(JSON.stringify(ticketResponsePayload)))
    return Promise.reject(new TypeError(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  const onRefreshTicket = vi.fn((ticketId: string) => client.fetchTicket(ticketId).then(() => undefined))
  renderedReview({ client, onRefreshTicket })

  // When: the reviewer records an obsolete reply.
  fireEvent.click(screen.getByRole('button', { name: /记录审核/ }))

  // Then: both command and reconciliation use the injected JWT client before retry is exposed.
  expect((await screen.findByRole('alert')).textContent).toContain('工单或分析已更新，请刷新后重新审核')
  expect(onRefreshTicket).toHaveBeenCalledWith('ticket-10042')
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/api/tickets/ticket-10042/analyses/analysis-1/reviews',
    expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer review-stale-token' }) }),
  ))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/api/tickets/ticket-10042',
    expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer review-stale-token' }) }),
  ))
})
