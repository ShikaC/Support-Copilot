// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiRequestError, type ApiClient } from '../../services/api'
import { analysisResultSchema, analysisReviewSchema, ticketResponseSchema } from '../../services/apiSchemas'
import type { TicketActivityPage } from '../../services/ticketWorkspaceSchemas'
import { analysisResponsePayload, analysisReviewPayload, ticketResponsePayload } from '../../test/apiFixtures'
import { TicketActivity } from './TicketActivity'

const ticket = ticketResponseSchema.parse(ticketResponsePayload)
afterEach(cleanup)
function page(ids: readonly string[], nextCursor: string | null = null): TicketActivityPage {
  return { items: ids.map((id) => ({ id, action: 'TICKET_UPDATED', actorLabel: 'trusted-operator', createdAt: '2026-09-10T02:00:00Z',
    traceId: `trace-${id}`, ticketVersion: 3, detail: id })), nextCursor }
}

it('loads durable pages in server order and deduplicates overlapping boundaries', async () => {
  const fetchTicketActivity = vi.fn<ApiClient['fetchTicketActivity']>()
    .mockResolvedValueOnce(page(['newest', 'boundary'], 'older-page')).mockResolvedValueOnce(page(['boundary', 'oldest']))
  render(<TicketActivity ticket={ticket} client={{ fetchTicketActivity }} />)
  await screen.findByText('newest')
  fireEvent.click(screen.getByRole('button', { name: '加载更早记录' }))
  await screen.findByText('oldest')
  expect(fetchTicketActivity.mock.calls[1]?.slice(0, 2)).toEqual([ticket.id, 'older-page'])
  expect(screen.getAllByRole('listitem').map((item) => item.querySelector('.timeline-label')?.textContent)).toEqual(['newest', 'boundary', 'oldest'])
  expect(screen.getAllByText('关联版本 3')).toHaveLength(3)
  expect(screen.getByText('trace-oldest')).toBeTruthy()
  expect(screen.queryByRole('button', { name: '加载更早记录' })).toBeNull()
})

it('cancels pending requests on ticket switches and ignores late results from the previous ticket', async () => {
  let resolvePrevious: (value: TicketActivityPage) => void = () => { throw new Error('Deferred request is not ready') }
  const previousRequest = new Promise<TicketActivityPage>((resolve) => { resolvePrevious = resolve })
  const fetchTicketActivity = vi.fn<ApiClient['fetchTicketActivity']>()
    .mockReturnValueOnce(previousRequest).mockResolvedValueOnce(page(['current-ticket-event']))
  const client = { fetchTicketActivity }
  const { rerender } = render(<TicketActivity ticket={ticket} client={client} />)
  await waitFor(() => expect(fetchTicketActivity).toHaveBeenCalledTimes(1))
  const previousSignal = fetchTicketActivity.mock.calls[0]?.[2]
  rerender(<TicketActivity ticket={{ ...ticket, id: 'other-ticket' }} client={client} />)
  await screen.findByText('current-ticket-event')
  await act(async () => { resolvePrevious(page(['previous-ticket-event'])) })
  expect(previousSignal?.aborted).toBe(true)
  expect(screen.queryByText('previous-ticket-event')).toBeNull()
  expect(screen.getByText('current-ticket-event')).toBeTruthy()
})

it('retains loaded events and retries the failed older-page cursor', async () => {
  const fetchTicketActivity = vi.fn<ApiClient['fetchTicketActivity']>()
    .mockResolvedValueOnce(page(['saved-event'], 'retry-cursor'))
    .mockRejectedValueOnce(new ApiRequestError('network')).mockResolvedValueOnce(page(['recovered-event']))
  render(<TicketActivity ticket={ticket} client={{ fetchTicketActivity }} />)
  await screen.findByText('saved-event')
  fireEvent.click(screen.getByRole('button', { name: '加载更早记录' }))
  await screen.findByRole('alert')
  expect(screen.getByText('saved-event')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '重新加载处理记录' }))
  await screen.findByText('recovered-event')
  expect(fetchTicketActivity.mock.calls[2]?.slice(0, 2)).toEqual([ticket.id, 'retry-cursor'])
  expect(screen.queryByRole('alert')).toBeNull()
})

it('reloads when ticket version, analysis identity or review identity changes', async () => {
  const fetchTicketActivity = vi.fn<ApiClient['fetchTicketActivity']>()
    .mockResolvedValueOnce(page(['initial-event'])).mockResolvedValueOnce(page(['note-event']))
    .mockResolvedValueOnce(page(['analysis-event'])).mockResolvedValueOnce(page(['review-event']))
  const client = { fetchTicketActivity }
  const { rerender } = render(<TicketActivity ticket={ticket} client={client} />)
  await screen.findByText('initial-event')
  const updated = { ...ticket, version: ticket.version + 1 }
  rerender(<TicketActivity ticket={updated} client={client} />)
  await screen.findByText('note-event')
  const analyzed = { ...updated, latestAnalysis: analysisResultSchema.parse(analysisResponsePayload('analysis-new')) }
  rerender(<TicketActivity ticket={analyzed} client={client} />)
  await screen.findByText('analysis-event')
  const reviewed = { ...analyzed, latestReview: analysisReviewSchema.parse(analysisReviewPayload('review-new')) }
  rerender(<TicketActivity ticket={reviewed} client={client} />)
  await screen.findByText('review-event')
  expect(fetchTicketActivity).toHaveBeenCalledTimes(4)
  expect(screen.queryByText('initial-event')).toBeNull()
  expect(screen.queryByText('analysis-event')).toBeNull()
})

it('does not fabricate legacy events when the durable feed is empty', async () => {
  const fetchTicketActivity = vi.fn<ApiClient['fetchTicketActivity']>().mockResolvedValue(page([]))
  render(<TicketActivity ticket={{ ...ticket, events: [{ id: 'synthetic', label: 'Fake creation', detail: 'FAKE_EVENT', createdAt: ticket.createdAt }] }} client={{ fetchTicketActivity }} />)
  await waitFor(() => expect(screen.getByRole('region', { name: '处理记录' }).getAttribute('aria-busy')).toBe('false'))
  expect(screen.queryAllByRole('listitem')).toHaveLength(0)
  expect(screen.queryByText('FAKE_EVENT')).toBeNull()
})
