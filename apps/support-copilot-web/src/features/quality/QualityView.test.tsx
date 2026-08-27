// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { metricsResponseSchema } from '../../services/apiSchemas'
import { metricsResponsePayload, nullableMetricsResponsePayload } from '../../test/apiFixtures'
import { QualityView } from './QualityView'

afterEach(cleanup)

it('renders backend quality evidence when available', () => {
  render(<QualityView metrics={metricsResponseSchema.parse(metricsResponsePayload)} metricsError={false} />)
  expect(screen.getAllByText('88.0%')).toHaveLength(2)
  expect(screen.getByText('tickets.jsonl')).toBeTruthy()
  expect(screen.getByText('通过')).toBeTruthy()
})

it('distinguishes unavailable quality evidence from request failure', () => {
  const { rerender } = render(<QualityView metrics={metricsResponseSchema.parse(nullableMetricsResponsePayload)} metricsError={false} />)
  expect(screen.getByText('质量指标暂不可用')).toBeTruthy()
  rerender(<QualityView metrics={null} metricsError />)
  expect(screen.getByText('质量指标请求失败')).toBeTruthy()
})
