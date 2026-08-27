// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../../auth/authSession'
import { createApiClient } from '../../services/api'
import { auditEventPayload } from '../../test/apiFixtures'
import { AuditView } from './AuditView'

afterEach(() => {
  cleanup()
  window.sessionStorage.clear()
  vi.unstubAllGlobals()
})

function securedClient() {
  const auth = createAuthSession({ mode: 'secured' })
  auth.setAccessToken('synthetic-test-token-audit')
  return createApiClient({ auth, baseUrl: '', timeoutMs: 1000 })
}

it('renders an empty audit page', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ items: [], nextCursor: null })))))
  render(<AuditView client={securedClient()} />)
  expect(screen.getByText('正在加载审计记录')).toBeTruthy()
  expect(await screen.findByText('暂无审计记录')).toBeTruthy()
})

it('appends a cursor page and preserves the outbound pagination contract', async () => {
  const secondEvent = { ...auditEventPayload, id: 'audit-2', targetId: 'review-2', traceId: 'trace-audit-2' }
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path === '/api/audit-events') return Promise.resolve(new Response(JSON.stringify({ items: [auditEventPayload], nextCursor: 'cursor-2' })))
    if (path === '/api/audit-events?cursor=cursor-2&limit=20') return Promise.resolve(new Response(JSON.stringify({ items: [secondEvent], nextCursor: null })))
    return Promise.reject(new TypeError(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<AuditView client={securedClient()} />)

  fireEvent.click(await screen.findByRole('button', { name: '加载更多' }))
  expect(await screen.findByText('trace-audit-2')).toBeTruthy()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/api/audit-events?cursor=cursor-2&limit=20',
    expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer synthetic-test-token-audit' }) }),
  ))
})

it('renders a ticket-unassigned ASSIGNEE audit event through the runtime client boundary', async () => {
  // Given: Java serializes the actual AuditChangedField enum value for an unassignment.
  const unassignedEvent = {
    ...auditEventPayload,
    id: 'audit-unassign-1',
    action: 'TICKET_UNASSIGNED',
    targetType: 'TICKET',
    targetId: 'ticket-10042',
    metadata: { changedFields: ['ASSIGNEE'] },
  }
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({
    items: [unassignedEvent],
    nextCursor: null,
  })))))

  // When: the rendered audit workflow loads that backend payload through ApiClient.
  render(<AuditView client={securedClient()} />)

  // Then: strict parsing accepts the wire contract and the page remains available.
  expect(await screen.findByText('trace-audit-1')).toBeTruthy()
  expect(screen.getByText('取消负责人')).toBeTruthy()
  expect(screen.queryByText('审计记录暂不可用')).toBeNull()
})
