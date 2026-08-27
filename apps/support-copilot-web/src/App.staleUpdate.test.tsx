// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import App from './App'
import { metricsResponsePayload, ticketResponsePayload } from './test/apiFixtures'

vi.mock('echarts-for-react', () => ({ default: () => null }))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('reloads and reconciles the affected ticket after a stale assignment update', async () => {
  class TestResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  const initialTicket = {
    ...ticketResponsePayload,
    status: 'IN_PROGRESS',
    assigneeName: '原负责人',
    version: 4,
  }
  const refreshedTicket = {
    ...initialTicket,
    assigneeName: '并发负责人',
    version: 5,
  }
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path === '/api/tickets' && init?.method === undefined) {
      return Promise.resolve(new Response(JSON.stringify([initialTicket]), { status: 200 }))
    }
    if (path === '/api/metrics') {
      return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload), { status: 200 }))
    }
    if (path === '/api/tickets/ticket-10042/unassign') {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            code: 'VERSION_CONFLICT',
            message: '工单已被其他操作更新，本次操作基于旧版本，未保存。',
            traceId: 'trace-stale-assignee',
            timestamp: '2026-08-27T00:00:00Z',
            details: { ticketId: 'ticket-10042', expectedVersion: 4, currentVersion: 5 },
          }),
          { status: 409 },
        ),
      )
    }
    if (path === '/api/tickets/ticket-10042') {
      return Promise.resolve(new Response(JSON.stringify(refreshedTicket), { status: 200 }))
    }
    return Promise.reject(new TypeError(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  await screen.findByText('原负责人')

  fireEvent.click(screen.getByRole('button', { name: '取消负责人' }))

  expect((await screen.findByRole('alert')).textContent).toContain(
    '工单已被其他操作更新，请刷新后再取消负责人',
  )
  expect(await screen.findByText('并发负责人')).toBeTruthy()
  await waitFor(() => {
    expect(fetchMock.mock.calls.some(([input]) => input === '/api/tickets/ticket-10042')).toBe(true)
  })
})

it('sends a versioned PATCH and reconciles a stale real-ticket assignment', async () => {
  class TestResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  const initialTicket = {
    ...ticketResponsePayload,
    status: 'NEW',
    assigneeName: null,
    version: 4,
  }
  const refreshedTicket = {
    ...initialTicket,
    assigneeName: '并发负责人',
    version: 5,
  }
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path === '/api/tickets' && init?.method === undefined) {
      return Promise.resolve(new Response(JSON.stringify([initialTicket]), { status: 200 }))
    }
    if (path === '/api/metrics') {
      return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload), { status: 200 }))
    }
    if (path === '/api/tickets/ticket-10042' && init?.method === 'PATCH') {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            code: 'VERSION_CONFLICT',
            message: '工单已被其他操作更新，本次操作基于旧版本，未保存。',
            traceId: 'trace-stale-assignment',
            timestamp: '2026-08-27T00:00:00Z',
            details: { ticketId: 'ticket-10042', expectedVersion: 4, currentVersion: 5 },
          }),
          { status: 409 },
        ),
      )
    }
    if (path === '/api/tickets/ticket-10042') {
      return Promise.resolve(new Response(JSON.stringify(refreshedTicket), { status: 200 }))
    }
    return Promise.reject(new TypeError(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  await screen.findByText('未分配')

  fireEvent.click(screen.getByRole('button', { name: '领取工单' }))

  expect((await screen.findByRole('alert')).textContent).toContain(
    '工单已被其他操作更新，请刷新后再更新负责人',
  )
  expect(await screen.findByText('并发负责人')).toBeTruthy()
  expect(fetchMock).toHaveBeenCalledWith('/api/tickets/ticket-10042', expect.objectContaining({
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assigneeName: '演示管理员', expectedVersion: 4 }),
    signal: expect.any(AbortSignal),
  }))
})
