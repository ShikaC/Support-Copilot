// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../auth/authSession'
import { createApiClient } from '../services/api'
import { ticketResponsePayload } from '../test/apiFixtures'
import { CommandPalette } from './CommandPalette'

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn() })) })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
function setup() {
  const onSelect = vi.fn()
  render(<CommandPalette client={createApiClient({ auth: createAuthSession({ mode: 'demo' }), baseUrl: '', timeoutMs: 8000 })} tickets={[]} onClose={vi.fn()} onNavigate={vi.fn()} onSelect={onSelect} />)
  return onSelect
}
it('finds and opens a server ticket absent from the loaded queue', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify([{ ...ticketResponsePayload, subject: '全量独有工单' }])))
  vi.stubGlobal('fetch', fetcher)
  const select = setup()
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '独有' } })
  fireEvent.click(await screen.findByRole('button', { name: /全量独有工单/ }))
  expect(select).toHaveBeenCalledWith(expect.objectContaining({ id: ticketResponsePayload.id, subject: '全量独有工单' }))
  const request = new URL(fetcher.mock.calls[0]?.[0], 'https://example.test')
  expect(request.searchParams.get('keyword')).toBe('独有')
  expect(request.searchParams.has('status')).toBe(false)
})
it('ignores an older response after the query changes and retries a failed search', async () => {
  let resolveOld: ((response: Response) => void) | undefined
  const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveOld = resolve }))
    .mockRejectedValueOnce(new TypeError('network unavailable'))
    .mockResolvedValueOnce(new Response(JSON.stringify([{ ...ticketResponsePayload, subject: '新结果' }])))
  vi.stubGlobal('fetch', fetcher)
  setup()
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '旧查询' } })
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1))
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '新查询' } })
  await screen.findByText('搜索暂不可用，请重试。')
  resolveOld?.(new Response(JSON.stringify([{ ...ticketResponsePayload, subject: '旧结果' }])))
  fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
  await screen.findByRole('button', { name: /新结果/ })
  expect(screen.queryByRole('button', { name: /旧结果/ })).toBeNull()
})
