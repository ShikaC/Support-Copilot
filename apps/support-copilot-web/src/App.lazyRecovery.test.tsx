// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { App } from './App'

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => vi.stubGlobal('ResizeObserver', TestResizeObserver))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('preserves the shell and retries a rejected lazy view loader', async () => {
  // Given: the overview chunk fails on its first load and succeeds on retry.
  const loader = vi.fn()
    .mockRejectedValueOnce(new TypeError('synthetic lazy load failure'))
    .mockResolvedValue({ OverviewView: () => <div>recovered overview</div> })
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
  render(<App authMode="demo" overviewLoader={loader} />)

  // When: the user opens the failed view and retries it.
  fireEvent.click(screen.getAllByRole('button', { name: '运营概览' })[0])
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(screen.getByRole('navigation', { name: '主导航' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '重试加载' }))

  // Then: the loader is invoked again and the recovered view replaces the error.
  expect(await screen.findByText('recovered overview')).toBeTruthy()
  expect(loader).toHaveBeenCalledTimes(2)
})
