// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../../auth/authSession'
import { createApiClient } from '../../services/api'
import { knowledgeHitPayload, knowledgeReleasePayload } from '../../test/apiFixtures'
import { KnowledgeView } from './KnowledgeView'

afterEach(() => {
  cleanup()
  window.sessionStorage.clear()
  vi.unstubAllGlobals()
})

function securedClient() {
  const auth = createAuthSession({ mode: 'secured' })
  auth.setAccessToken('synthetic-test-token-knowledge')
  return createApiClient({ auth, baseUrl: '', timeoutMs: 1000 })
}

it('renders strict search results as text, sends query parameters, and exposes empty results', async () => {
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path === '/api/knowledge/search?query=&topK=10') return Promise.resolve(new Response(JSON.stringify([knowledgeHitPayload])))
    if (path === '/api/knowledge/search?query=missing&topK=10') return Promise.resolve(new Response(JSON.stringify([])))
    if (path === '/api/knowledge/releases') return Promise.resolve(new Response(JSON.stringify([knowledgeReleasePayload])))
    return Promise.reject(new TypeError(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<KnowledgeView client={securedClient()} demoArticles={null} />)

  expect(screen.getByText('正在加载知识目录')).toBeTruthy()
  expect(await screen.findByText(knowledgeHitPayload.content)).toBeTruthy()
  expect(document.querySelector('img')).toBeNull()
  fireEvent.change(screen.getByPlaceholderText('搜索已授权知识'), { target: { value: 'missing' } })
  fireEvent.click(screen.getByRole('button', { name: /搜\s*索/ }))
  expect(await screen.findByText('没有匹配的知识证据')).toBeTruthy()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/api/knowledge/search?query=missing&topK=10',
    expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer synthetic-test-token-knowledge' }) }),
  ))
})

it('sends expectedVersion and becomes read-only when a release command returns 403', async () => {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (path.startsWith('/api/knowledge/search?')) return Promise.resolve(new Response(JSON.stringify([knowledgeHitPayload])))
    if (path === '/api/knowledge/releases') return Promise.resolve(new Response(JSON.stringify([knowledgeReleasePayload])))
    if (path === '/api/knowledge/releases/release-2026-08/approve') return Promise.resolve(new Response(JSON.stringify({ code: 'ACCESS_DENIED', message: 'Forbidden', traceId: 'trace-release-403' }), { status: 403 }))
    return Promise.reject(new TypeError(`Unexpected request: ${path}:${init?.method ?? 'GET'}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<KnowledgeView client={securedClient()} demoArticles={null} />)

  fireEvent.click(await screen.findByRole('button', { name: /批\s*准/ }))
  expect(await screen.findByText('当前身份仅可查看知识发布')).toBeTruthy()
  expect(screen.getByRole('button', { name: /批\s*准/ }).hasAttribute('disabled')).toBe(true)
  expect(fetchMock).toHaveBeenCalledWith('/api/knowledge/releases/release-2026-08/approve', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ expectedVersion: 2 }),
  }))
})
