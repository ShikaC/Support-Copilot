// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { demoMetrics, demoTickets } from '../../data/demoData'
import { OverviewView } from './OverviewView'

vi.mock('echarts-for-react/esm/core', () => ({
  default: ({ option }: { readonly option: { readonly animation?: boolean } }) => (
    <div data-testid="chart-renderer" data-animation-enabled={String(option.animation)} />
  ),
}))

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn((query: string): MediaQueryList => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(() => true),
    })),
  })
})

it('provides textual chart equivalents and disables chart motion when reduced motion is requested', () => {
  // Given: metrics with trend and category chart data and an OS reduced-motion preference.
  // When: the overview is rendered.
  render(<OverviewView metrics={demoMetrics} tickets={demoTickets} />)

  // Then: both charts expose equivalent tables and render without chart animation.
  expect(screen.getByRole('table', { name: '工单趋势数据' })).toBeTruthy()
  expect(screen.getByRole('table', { name: '类别分布数据' })).toBeTruthy()
  for (const chart of screen.getAllByTestId('chart-renderer')) {
    expect(chart.getAttribute('data-animation-enabled')).toBe('false')
  }
})
