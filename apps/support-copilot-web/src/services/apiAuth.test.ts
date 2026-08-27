import { afterEach, expect, it, vi } from 'vitest'

import { createAuthSession } from '../auth/authSession'
import { ticketResponsePayload } from '../test/apiFixtures'
import { ApiContractError, ApiRequestError, createApiClient } from './api'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function ticketResponse() {
  return new Response(JSON.stringify([ticketResponsePayload]), { status: 200 })
}

it('injects a session-scoped token only in secured authenticated mode', async () => {
  const auth = createAuthSession({ mode: 'secured' })
  auth.setAccessToken('synthetic.jwt.token')
  const fetchMock = vi.fn().mockResolvedValue(ticketResponse())
  vi.stubGlobal('fetch', fetchMock)

  await createApiClient({ auth, baseUrl: '', timeoutMs: 1000 }).fetchTickets()

  expect(fetchMock).toHaveBeenCalledWith('/api/tickets', {
    headers: {
      Authorization: 'Bearer synthetic.jwt.token',
      'Content-Type': 'application/json',
    },
    signal: expect.any(AbortSignal),
  })
  expect(auth.state()).toEqual({ mode: 'secured', status: 'authenticated' })
})

it('omits authorization when secured mode has no token', async () => {
  const auth = createAuthSession({ mode: 'secured' })
  const fetchMock = vi.fn().mockResolvedValue(ticketResponse())
  vi.stubGlobal('fetch', fetchMock)

  await createApiClient({ auth, baseUrl: '', timeoutMs: 1000 }).fetchTickets()

  expect(fetchMock).toHaveBeenCalledWith('/api/tickets', {
    headers: { 'Content-Type': 'application/json' },
    signal: expect.any(AbortSignal),
  })
  expect(auth.state()).toEqual({ mode: 'secured', status: 'unauthenticated' })
})

it('classifies explicit cancellation and leaves a later request usable', async () => {
  const auth = createAuthSession({ mode: 'secured' })
  const controller = new AbortController()
  const fetchMock = vi
    .fn()
    .mockImplementationOnce((_path: string, init: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })
      }),
    )
    .mockResolvedValueOnce(ticketResponse())
  vi.stubGlobal('fetch', fetchMock)
  const client = createApiClient({ auth, baseUrl: '', timeoutMs: 1000 })

  const cancelled = client.fetchTickets({ signal: controller.signal })
  controller.abort()

  await expect(cancelled).rejects.toMatchObject({ name: 'ApiRequestError', kind: 'cancelled' })
  await expect(client.fetchTickets()).resolves.toHaveLength(1)
})

it('bounds requests by timeout without leaking the access token', async () => {
  vi.useFakeTimers()
  const token = 'secret-token-must-not-leak'
  const auth = createAuthSession({ mode: 'secured' })
  auth.setAccessToken(token)
  vi.stubGlobal(
    'fetch',
    vi.fn((_path: string, init: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })
      }),
    ),
  )
  const request = createApiClient({ auth, baseUrl: '', timeoutMs: 25 }).fetchTickets()

  await vi.advanceTimersByTimeAsync(25)

  const error = await request.catch((caught: unknown) => caught)
  expect(error).toBeInstanceOf(ApiRequestError)
  expect(error).toMatchObject({ kind: 'timeout' })
  expect(String(error)).not.toContain(token)
  expect(JSON.stringify(error)).not.toContain(token)
})

it('fails closed when an HTTP error envelope has unknown fields', async () => {
  const auth = createAuthSession({ mode: 'demo' })
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 'ACCESS_DENIED',
          message: 'denied',
          traceId: 'trace-auth',
          rawToken: 'must-not-cross',
        }),
        { status: 403 },
      ),
    ),
  )

  const request = createApiClient({ auth, baseUrl: '', timeoutMs: 1000 }).fetchTickets()

  await expect(request).rejects.toBeInstanceOf(ApiContractError)
  await expect(request).rejects.toMatchObject({ issues: [{ code: 'invalid_union' }] })
})
