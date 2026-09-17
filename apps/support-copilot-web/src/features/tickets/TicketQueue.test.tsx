// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ticketResponseSchema } from '../../services/apiSchemas'
import { pendingTicketQuery } from '../../services/ticketWorkspaceSchemas'
import { ticketResponsePayload } from '../../test/apiFixtures'
import type { Ticket } from '../../types'
import { TicketQueue } from './TicketQueue'

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
beforeEach(() => vi.stubGlobal('ResizeObserver', TestResizeObserver))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const ticket = ticketResponseSchema.parse(ticketResponsePayload)
const serverTickets: readonly Ticket[] = [
  { ...ticket, id: 'older', ticketNo: 'SC-OLDER', createdAt: '2026-01-01T00:00:00Z', slaDeadline: '2026-01-09T00:00:00Z', status: 'NEW' },
  { ...ticket, id: 'newer', ticketNo: 'SC-NEWER', createdAt: '2026-01-02T00:00:00Z', slaDeadline: '2026-01-03T00:00:00Z', status: 'NEW' },
]
function renderQueue(tickets: readonly Ticket[] = serverTickets) {
  const onQuery = vi.fn()
  render(<TicketQueue tickets={tickets} selectedTicketId="older" onSelect={vi.fn()} onCreate={vi.fn()}
    onQuery={onQuery} nextCursor="next" onLoadMore={vi.fn()} loading={false} error={false} onRetry={vi.fn()} totalCount={35} />)
  return onQuery
}
function choose(label: string, option: string) {
  fireEvent.mouseDown(screen.getByRole('combobox', { name: label }))
  fireEvent.click(screen.getByText(option))
}

it('preserves server order and shows the global matching total rather than sorting the loaded subset', async () => {
  const onQuery = renderQueue()
  expect(screen.getByText('已加载 2 / 共 35 条')).toBeTruthy()
  expect([...document.querySelectorAll('.ticket-no')].map((item) => item.textContent)).toEqual(['SC-OLDER', 'SC-NEWER'])

  choose('队列排序', 'SLA 最紧急')

  await waitFor(() => expect(onQuery).toHaveBeenLastCalledWith(expect.objectContaining({ sort: 'SLA', status: pendingTicketQuery.status })))
  expect([...document.querySelectorAll('.ticket-no')].map((item) => item.textContent)).toEqual(['SC-OLDER', 'SC-NEWER'])
})

it('sends priority sort and unassigned filter to the server while preserving the pending scope', async () => {
  const onQuery = renderQueue()

  choose('队列排序', '优先级最高')
  choose('按负责人筛选', '未分配负责人')

  await waitFor(() => expect(onQuery).toHaveBeenLastCalledWith(expect.objectContaining({
    sort: 'PRIORITY', assignee: 'UNASSIGNED', status: pendingTicketQuery.status,
  })))
})

it('queries an exact trimmed assignee and description keyword, then clears the assignee filter', async () => {
  const onQuery = renderQueue()
  choose('按负责人筛选', '指定负责人')
  fireEvent.change(screen.getByRole('textbox', { name: '负责人姓名' }), { target: { value: ' 专员甲 ' } })
  fireEvent.change(screen.getByRole('textbox', { name: '搜索工单' }), { target: { value: ' 正文关键字 ' } })
  await waitFor(() => expect(onQuery).toHaveBeenLastCalledWith(expect.objectContaining({ assignee: '专员甲', keyword: '正文关键字' })))

  choose('按负责人筛选', '全部负责人')

  await waitFor(() => expect(onQuery).toHaveBeenLastCalledWith(expect.objectContaining({ assignee: '', keyword: '正文关键字' })))
  expect(screen.queryByRole('textbox', { name: '负责人姓名' })).toBeNull()
})

it('sorts only explicit versionless preview tickets locally', async () => {
  const previewTickets = serverTickets.map(({ version: _version, ...preview }) => preview)
  renderQueue(previewTickets)

  choose('队列排序', 'SLA 最紧急')

  await waitFor(() => expect(screen.getByText('本地预览 · 2 条')).toBeTruthy())
  expect([...document.querySelectorAll('.ticket-no')].map((item) => item.textContent)).toEqual(['SC-NEWER', 'SC-OLDER'])
})
