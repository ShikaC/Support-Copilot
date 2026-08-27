// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import App from './App'

vi.mock('echarts-for-react', () => ({ default: () => null }))

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('renders secured unauthenticated truth and an audit role state without demo identity', async () => {
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string | URL | Request) => {
      const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
      const forbidden = path === '/api/audit-events'
      return Promise.resolve(new Response(JSON.stringify({
        code: forbidden ? 'ACCESS_DENIED' : 'AUTHENTICATION_REQUIRED',
        message: forbidden ? 'The authenticated user does not have the required role.' : 'Authentication is required.',
        traceId: forbidden ? 'trace-audit-denied' : 'trace-auth-required',
      }), { status: forbidden ? 403 : 401 }))
    }),
  )

  render(<App authMode="secured" />)

  expect(await screen.findByText('需要登录')).toBeTruthy()
  expect(screen.queryByText('演示管理员')).toBeNull()
  fireEvent.click(screen.getAllByRole('button', { name: '审计记录' })[0])
  expect(await screen.findByText('需要审核员或管理员权限')).toBeTruthy()
})

it('never labels a secured service failure as demo data', async () => {
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('offline'))))

  render(<App authMode="secured" />)

  expect(await screen.findByText('安全服务不可用')).toBeTruthy()
  expect(screen.queryByText('演示数据模式')).toBeNull()
  expect(screen.queryByText('演示管理员')).toBeNull()
})
