import liveReport from '../../../../tests/fixtures/quality-reports/live.json'
import businessReport from '../../../../tests/fixtures/quality-reports/business.json'
import { afterEach, expect, it, vi } from 'vitest'
import { createAuthSession } from '../auth/authSession'
import { ApiContractError, createApiClient } from './api'
import { qualityReportsSchema } from './qualityReports'
import { qualityReportsFixture } from '../features/quality/qualityTestFixture'

afterEach(() => vi.unstubAllGlobals())

it('accepts shared synthetic report contracts with independent failure outcomes', () => {
  const parsed = qualityReportsSchema.parse({ liveEvaluation: { status: 'AVAILABLE', report: liveReport }, businessBenchmark: { status: 'AVAILABLE', report: businessReport } })
  expect(parsed.liveEvaluation.report?.outcomes).toEqual({ normalLive: 1, evidenceInsufficient: 1, timeout: 1, otherFallback: 0, error: 0 })
  expect(parsed.businessBenchmark.report).toMatchObject({ sampleCount: 6, distinctCaseCount: 3, humanReviewedCount: 0, answerAccuracy: null, outcomes: { normalLive: 2, evidenceInsufficient: 2, timeout: 2, otherFallback: 0, error: 0 } })
  expect(parsed.businessBenchmark.report?.groups.map((group) => group.concurrency)).toEqual([1, 2])
})

it('rejects a claimed normal success with unreconciled failure count', () => {
  const report = qualityReportsFixture.businessBenchmark.report
  const payload = { ...qualityReportsFixture, businessBenchmark: { status: 'AVAILABLE', report: { ...report, outcomes: { ...report.outcomes, normalLive: 3, timeout: 0, evidenceInsufficient: 0 } } } }
  expect(qualityReportsSchema.safeParse(payload).success).toBe(false)
})

it('rejects fabricated accuracy and malformed available status', () => {
  expect(qualityReportsSchema.safeParse({ ...qualityReportsFixture, liveEvaluation: { status: 'AVAILABLE', report: null } }).success).toBe(false)
  const report = qualityReportsFixture.businessBenchmark.report
  expect(qualityReportsSchema.safeParse({ ...qualityReportsFixture, businessBenchmark: { status: 'AVAILABLE', report: { ...report, answerAccuracy: 0.9 } } }).success).toBe(false)
})

it('uses the current authenticated client for quality evidence', async () => {
  const storage = { getItem: () => null, setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn(), key: () => null, length: 0 }
  const auth = createAuthSession({ mode: 'secured', storage })
  const client = createApiClient({ auth, baseUrl: '', timeoutMs: 1000 })
  auth.setAccessToken('quality-token-test-only')
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(qualityReportsFixture)))
  vi.stubGlobal('fetch', fetchMock)
  await client.getQualityReports()
  expect(fetchMock).toHaveBeenCalledWith('/api/quality-reports', expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer quality-token-test-only' }) }))
})

it('rejects invalid quality payload rather than returning placeholder data', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')))
  const client = createApiClient({ auth: createAuthSession({ mode: 'demo' }), baseUrl: '', timeoutMs: 1000 })
  await expect(client.getQualityReports()).rejects.toBeInstanceOf(ApiContractError)
})

it.each([
  { humanReviewedCount: 1 },
  { failures: [{ caseId: 'case-timeout', concurrency: null, outcome: 'TIMEOUT', reason: 'ReadTimeout', traceId: null }, ...qualityReportsFixture.businessBenchmark.report.failures.slice(1)] },
  { outcomes: { normalLive: 1, evidenceInsufficient: 0, timeout: 2, otherFallback: 0, error: 0 } },
  { sourceFiles: [{ name: '../secret.json', sha256: 'a'.repeat(64) }] },
  { groups: [{ ...qualityReportsFixture.businessBenchmark.report.groups[0], p50Ms: 3000, p95Ms: 2000 }] },
  { groups: [{ ...qualityReportsFixture.businessBenchmark.report.groups[0], persisted: 4 }] },
])('rejects incoherent evidence mutation %#', (mutation) => {
  const report = { ...qualityReportsFixture.businessBenchmark.report, ...mutation }
  expect(qualityReportsSchema.safeParse({ ...qualityReportsFixture, businessBenchmark: { status: 'AVAILABLE', report } }).success).toBe(false)
})
