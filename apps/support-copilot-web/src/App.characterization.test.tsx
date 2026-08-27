// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import App from './App'
import { metricsResponsePayload, ticketResponsePayload } from './test/apiFixtures'

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

it('preserves the established four-view console structure before extraction', async () => {
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string | URL | Request) => {
      const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
      if (path === '/api/tickets') {
        return Promise.resolve(new Response(JSON.stringify([ticketResponsePayload]), { status: 200 }))
      }
      if (path === '/api/metrics') {
        return Promise.resolve(new Response(JSON.stringify(metricsResponsePayload), { status: 200 }))
      }
      return Promise.reject(new TypeError(`Unexpected request: ${path}`))
    }),
  )

  render(<App />)

  expect(await screen.findByRole('region', { name: '工单队列' })).toBeTruthy()
  expect(screen.getByRole('region', { name: '工单详情' })).toBeTruthy()
  expect(screen.getByText('运行分析后将在这里显示处理轨迹与知识证据')).toBeTruthy()

  fireEvent.click(screen.getAllByRole('button', { name: '运营概览' })[0])
  expect(await screen.findByText('工单趋势')).toBeTruthy()

  fireEvent.click(screen.getAllByRole('button', { name: '知识库' })[0])
  expect(await screen.findByRole('heading', { name: '知识服务暂不可用' })).toBeTruthy()

  fireEvent.click(screen.getAllByRole('button', { name: '质量评估' })[0])
  expect(await screen.findByText('评估运行')).toBeTruthy()
})
