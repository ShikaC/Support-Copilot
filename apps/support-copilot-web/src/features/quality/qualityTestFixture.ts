import type { QualityReports } from '../../services/qualityReports'
export const qualityReportsFixture = {
  liveEvaluation: { status: 'INVALID', report: null },
  businessBenchmark: { status: 'AVAILABLE', report: {
    schemaVersion: 1, id: 'test-business', kind: 'BUSINESS_BENCHMARK', title: '测试业务基准', dataset: '测试数据', generatedAt: '2026-09-10T00:00:00Z',
    sourceFiles: [{ name: 'test/summary.json', sha256: 'a'.repeat(64) }], sampleCount: 3, distinctCaseCount: 3, humanReviewedCount: 0,
    answerAccuracy: null, businessResolutionRate: null, timeSavedMinutes: null, cost: null,
    outcomes: { normalLive: 1, evidenceInsufficient: 1, timeout: 1, otherFallback: 0, error: 0 }, metrics: [],
    groups: [{ concurrency: 1, total: 3, normalLive: 1, evidenceInsufficient: 1, timeout: 1, otherFallback: 0, error: 0, p50Ms: 1000, p95Ms: 2000, apiCompleted: 3, persisted: 3 }],
    failures: [{ caseId: 'case-timeout', concurrency: 1, outcome: 'TIMEOUT', reason: 'ReadTimeout', traceId: 'trace-timeout' }, { caseId: 'case-insufficient', concurrency: 1, outcome: 'EVIDENCE_INSUFFICIENT', reason: 'insufficient', traceId: 'trace-insufficient' }],
    gateReasons: ['人工审核未完成'], limitations: ['仅测试样本'],
  } },
} satisfies QualityReports
