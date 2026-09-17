// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { getQualityReports, ApiRequestError } from '../../services/api'
import { metricsResponseSchema } from '../../services/apiSchemas'
import { metricsResponsePayload, nullableMetricsResponsePayload } from '../../test/apiFixtures'
import { QualityView } from './QualityView'
import { qualityReportsFixture } from './qualityTestFixture'

vi.mock('../../services/api', async (importOriginal) => ({ ...await importOriginal<typeof import('../../services/api')>(), getQualityReports: vi.fn() }))
afterEach(cleanup)
beforeEach(() => vi.mocked(getQualityReports).mockResolvedValue({ liveEvaluation: { status: 'NOT_CONFIGURED', report: null }, businessBenchmark: { status: 'NOT_CONFIGURED', report: null } }))

it('renders legacy backend evidence while reports are not configured', async () => {
  render(<QualityView metrics={metricsResponseSchema.parse(metricsResponsePayload)} metricsError={false} />)
  expect(await screen.findByText('tickets.jsonl')).toBeTruthy()
  expect(screen.getAllByText('88.0%')).toHaveLength(2)
})

it('keeps legacy absence distinct from request failure', async () => {
  const { rerender } = render(<QualityView metrics={metricsResponseSchema.parse(nullableMetricsResponsePayload)} metricsError={false} />)
  expect(await screen.findByText('质量指标暂不可用')).toBeTruthy()
  rerender(<QualityView metrics={null} metricsError />)
  expect(screen.getByText('质量指标请求失败')).toBeTruthy()
})

it('shows independently available reports even when metrics fail', async () => {
  vi.mocked(getQualityReports).mockResolvedValue(qualityReportsFixture)
  render(<QualityView metrics={null} metricsError />)
  expect(await screen.findByRole('heading', { name: '测试业务基准' })).toBeTruthy()
  expect(screen.getByText('人工审核 0 / 3')).toBeTruthy()
  expect(screen.getByText('回答准确率')).toBeTruthy()
  expect(screen.getByText('尚未测得')).toBeTruthy()
  expect(screen.getByText('报告校验失败')).toBeTruthy()
})

it('filters complete failure records and resets without treating timeout as success', async () => {
  vi.mocked(getQualityReports).mockResolvedValue(qualityReportsFixture)
  render(<QualityView metrics={null} metricsError={false} />)
  fireEvent.click(await screen.findByText('失败与降级明细 · 2'))
  fireEvent.click(screen.getByRole('button', { name: '模型超时' }))
  const failures = screen.getByRole('region', { name: '失败与降级记录' })
  expect(within(failures).getByText('case-timeout')).toBeTruthy()
  expect(within(failures).queryByText('case-insufficient')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '全部' }))
  expect(within(failures).getByText('case-insufficient')).toBeTruthy()
})

it('retries a failed evidence request without replacing it with mock data', async () => {
  vi.mocked(getQualityReports).mockRejectedValueOnce(new ApiRequestError('network')).mockResolvedValueOnce(qualityReportsFixture)
  render(<QualityView metrics={null} metricsError={false} />)
  expect(await screen.findByText('评估报告请求失败')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '重试加载报告' }))
  expect(await screen.findByRole('heading', { name: '测试业务基准' })).toBeTruthy()
})

it('labels live legacy retrieval and citations as process rules, not accuracy', async () => {
  const metrics = metricsResponseSchema.parse(metricsResponsePayload)
  if (metrics.evaluation === null) throw new TypeError('Expected evaluation fixture')
  render(<QualityView metrics={{ ...metrics, evaluation: { ...metrics.evaluation, mode: 'live' } }} metricsError={false} />)
  expect(await screen.findAllByText('检索流程成功率')).toHaveLength(2)
  expect(screen.getByText('引用规则通过率')).toBeTruthy()
  expect(screen.queryByText(/^Hit@/)).toBeNull()
})

it('explains known gates while preserving codes and surfacing unknown ones', async () => {
  const report = qualityReportsFixture.businessBenchmark.report
  vi.mocked(getQualityReports).mockResolvedValue({ ...qualityReportsFixture, businessBenchmark: { status: 'AVAILABLE', report: { ...report, gateReasons: ['machine-gate-failed', 'human-review-incomplete', 'reference-inputs-need-audit', 'provider-timeouts-observed', 'future-gate'] } } })
  render(<QualityView metrics={null} metricsError={false} />)
  expect(await screen.findByTitle('machine-gate-failed')).toHaveProperty('textContent', '自动规则检查未通过，请查看失败案例与指标。')
  expect(screen.getByTitle('human-review-incomplete').textContent).not.toBe('human-review-incomplete')
  expect(screen.getByTitle('reference-inputs-need-audit').textContent).not.toBe('reference-inputs-need-audit')
  expect(screen.getByTitle('provider-timeouts-observed').textContent).not.toBe('provider-timeouts-observed')
  expect(screen.getByTitle('future-gate').textContent).toBe('未知门禁代码：future-gate')
})


it.each(['MISSING', 'INVALID'] as const)('does not replace %s evidence with old mock metrics', async (status) => {
  vi.mocked(getQualityReports).mockResolvedValue({ ...qualityReportsFixture, liveEvaluation: { status, report: null } })
  render(<QualityView metrics={metricsResponseSchema.parse(metricsResponsePayload)} metricsError={false} />)
  await screen.findByRole('heading', { name: '测试业务基准' })
  expect(screen.queryByText('tickets.jsonl')).toBeNull()
})

it('does not replace a report network failure with old mock metrics', async () => {
  vi.mocked(getQualityReports).mockRejectedValueOnce(new ApiRequestError('network'))
  render(<QualityView metrics={metricsResponseSchema.parse(metricsResponsePayload)} metricsError={false} />)
  await screen.findByText('评估报告请求失败')
  expect(screen.queryByText('tickets.jsonl')).toBeNull()
})

it('keeps metric descriptions inside semantic definitions', async () => {
  const report = qualityReportsFixture.businessBenchmark.report
  vi.mocked(getQualityReports).mockResolvedValue({ ...qualityReportsFixture, businessBenchmark: { status: 'AVAILABLE', report: { ...report, metrics: [{ id: 'completed', label: '流程完成率', value: 1, unit: 'RATE', denominator: 3, description: '测试指标说明' }] } } })
  const { container } = render(<QualityView metrics={null} metricsError={false} />)
  const description = await screen.findByText('测试指标说明 · 分母 3')
  expect(description.closest('dd')).not.toBeNull()
  expect(container.querySelector('dl > div > p')).toBeNull()
})
