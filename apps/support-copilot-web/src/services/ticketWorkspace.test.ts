import { afterEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../auth/authSession'
import { createApiClient } from './api'
import { ticketResponsePayload } from '../test/apiFixtures'
import { createTicketSchema } from './ticketWorkspaceSchemas'

afterEach(() => vi.unstubAllGlobals())
const client = () => createApiClient({ auth: createAuthSession({ mode: 'demo' }), baseUrl: '', timeoutMs: 8000 })
it('reads the continuation cursor and sends encoded server filters', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify([ticketResponsePayload]), { headers: { 'X-Next-Cursor': 'cursor-next', 'X-Total-Count': '101' } }))
  vi.stubGlobal('fetch', fetcher)
  const page = await client().fetchTicketPage({ keyword: '账单 & SLA', priority: 'HIGH', cursor: 'cursor+1', sort: 'SLA', assignee: '客服 & A' })
  expect(page.nextCursor).toBe('cursor-next')
  expect(page.totalCount).toBe(101)
  expect(page.items[0]?.id).toBe(ticketResponsePayload.id)
  const request = new URL(fetcher.mock.calls[0]?.[0], 'https://example.test')
  expect(request.searchParams.get('keyword')).toBe('账单 & SLA')
  expect(request.searchParams.get('cursor')).toBe('cursor+1')
  expect(request.searchParams.get('sort')).toBe('SLA')
  expect(request.searchParams.get('assignee')).toBe('客服 & A')
})
it('validates and trims create input before sending to the service', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(ticketResponsePayload)))
  vi.stubGlobal('fetch', fetcher)
  await client().createTicket({ subject: ' 新工单 ', customerName: ' 客户 ', customerCompany: ' 企业 ', description: ' 描述 ', channel: 'EMAIL', customerTier: 'STANDARD', language: 'zh-CN' })
  expect(JSON.parse(fetcher.mock.calls[0]?.[1].body)).toEqual({ subject: '新工单', customerName: '客户', customerCompany: '企业', description: '描述', channel: 'EMAIL', customerTier: 'STANDARD', language: 'zh-CN' })
  expect(createTicketSchema.safeParse({ subject: ' ' }).success).toBe(false)
})
it('sends an internal note UUID and expected version', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: '23456789-1234-4234-8234-123456789abc', ticketId: ticketResponsePayload.id, content: '内部结论', authorLabel: '客服', createdAt: '2026-09-09T01:00:00Z' })))
  vi.stubGlobal('fetch', fetcher)
  await client().addTicketNote(ticketResponsePayload.id, '内部结论', 3, '23456789-1234-4234-8234-123456789abc')
  expect(JSON.parse(fetcher.mock.calls[0]?.[1].body)).toEqual({ content: '内部结论', expectedVersion: 3, noteId: '23456789-1234-4234-8234-123456789abc' })
})

it('reuses the creation idempotency key after an ambiguous network failure', async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('connection lost'))
    .mockResolvedValueOnce(new Response(JSON.stringify(ticketResponsePayload)))
  vi.stubGlobal('fetch', fetcher)
  const api = client()
  const input = { subject: '重试工单', customerName: '客户', customerCompany: '企业', description: '描述', channel: 'EMAIL', customerTier: 'STANDARD', language: 'zh-CN' } as const
  await expect(api.createTicket(input)).rejects.toThrow()
  await api.createTicket(input)
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/tickets/commands/create')
  const first = new Headers(fetcher.mock.calls[0]?.[1].headers).get('Idempotency-Key')
  expect(first).toBeTruthy()
  expect(new Headers(fetcher.mock.calls[1]?.[1].headers).get('Idempotency-Key')).toBe(first)
})
