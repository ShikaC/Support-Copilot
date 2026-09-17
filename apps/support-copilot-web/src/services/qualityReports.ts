import * as z from 'zod'

const count = z.number().int().nonnegative()
const positiveCount = count.positive()
const quantity = z.number().nonnegative()
const outcomes = z.strictObject({ normalLive: count, evidenceInsufficient: count, timeout: count, otherFallback: count, error: count })
const metric = z.strictObject({
  id: z.string().min(1), label: z.string().min(1), value: quantity.nullable(), unit: z.enum(['RATE', 'MS', 'NUMBER']),
  denominator: positiveCount.nullable(), description: z.string().min(1),
}).refine((value) => value.unit !== 'RATE' || value.value === null || value.value <= 1)

export const qualityReportSchema = z.strictObject({
  schemaVersion: z.literal(1), id: z.string().min(1), kind: z.enum(['LIVE_EVALUATION', 'BUSINESS_BENCHMARK']),
  title: z.string().min(1), dataset: z.string().min(1), generatedAt: z.iso.datetime(),
  sourceFiles: z.array(z.strictObject({ name: z.string().min(1).refine((name) => !name.includes('\\') && name.split('/').every((segment) => segment !== '' && segment !== '.' && segment !== '..')), sha256: z.string().regex(/^[a-f0-9]{64}$/) })).min(1),
  sampleCount: positiveCount, distinctCaseCount: positiveCount, humanReviewedCount: z.literal(0),
  answerAccuracy: z.null(), businessResolutionRate: z.null(), timeSavedMinutes: z.null(), cost: z.null(),
  outcomes, metrics: z.array(metric),
  groups: z.array(z.strictObject({ concurrency: positiveCount, total: positiveCount, ...outcomes.shape, p50Ms: quantity, p95Ms: quantity, apiCompleted: count, persisted: count })),
  failures: z.array(z.strictObject({ caseId: z.string().min(1), concurrency: positiveCount.nullable(), outcome: z.enum(['EVIDENCE_INSUFFICIENT', 'TIMEOUT', 'OTHER_FALLBACK', 'ERROR']), reason: z.string().min(1), traceId: z.string().min(1).nullable() })),
  gateReasons: z.array(z.string().min(1)), limitations: z.array(z.string().min(1)),
}).refine((report) => {
  const total = (values: z.infer<typeof outcomes>): number => Object.values(values).reduce((sum, value) => sum + value, 0)
  const unique = (values: readonly (string | number)[]): boolean => new Set(values).size === values.length
  if (report.distinctCaseCount > report.sampleCount || total(report.outcomes) !== report.sampleCount
    || report.failures.length !== report.sampleCount - report.outcomes.normalLive
    || !unique(report.sourceFiles.map((source) => source.name)) || !unique(report.metrics.map((value) => value.id))
    || report.metrics.some((value) => value.denominator !== null && value.denominator > report.sampleCount)
    || !unique(report.failures.map((value) => `${value.caseId}:${value.concurrency}`))) return false
  const failureCountsMatch = (values: z.infer<typeof outcomes>, failures: typeof report.failures): boolean =>
    values.evidenceInsufficient === failures.filter((value) => value.outcome === 'EVIDENCE_INSUFFICIENT').length
    && values.timeout === failures.filter((value) => value.outcome === 'TIMEOUT').length
    && values.otherFallback === failures.filter((value) => value.outcome === 'OTHER_FALLBACK').length
    && values.error === failures.filter((value) => value.outcome === 'ERROR').length
  if (!failureCountsMatch(report.outcomes, report.failures)) return false
  if (report.kind === 'LIVE_EVALUATION') return report.groups.length === 0 && report.failures.every((failure) => failure.concurrency === null)
  if (report.groups.length === 0 || !unique(report.groups.map((group) => group.concurrency))
    || report.groups.reduce((sum, group) => sum + group.total, 0) !== report.sampleCount) return false
  const keys = ['normalLive', 'evidenceInsufficient', 'timeout', 'otherFallback', 'error'] as const
  return keys.every((key) => report.groups.reduce((sum, group) => sum + group[key], 0) === report.outcomes[key])
    && report.groups.every((group) => total({ normalLive: group.normalLive, evidenceInsufficient: group.evidenceInsufficient, timeout: group.timeout, otherFallback: group.otherFallback, error: group.error }) === group.total
      && group.persisted <= group.apiCompleted && group.apiCompleted <= group.total && group.p50Ms <= group.p95Ms
      && failureCountsMatch(group, report.failures.filter((failure) => failure.concurrency === group.concurrency)))
    && report.failures.every((failure) => failure.concurrency !== null && report.groups.some((group) => group.concurrency === failure.concurrency))
}, { message: 'Report evidence does not reconcile' })

const slot = z.discriminatedUnion('status', [
  z.strictObject({ status: z.literal('AVAILABLE'), report: qualityReportSchema }),
  z.strictObject({ status: z.enum(['NOT_CONFIGURED', 'MISSING', 'INVALID']), report: z.null() }),
])
export const qualityReportsSchema = z.strictObject({ liveEvaluation: slot, businessBenchmark: slot })
  .refine((response) => (response.liveEvaluation.report === null || response.liveEvaluation.report.kind === 'LIVE_EVALUATION')
    && (response.businessBenchmark.report === null || response.businessBenchmark.report.kind === 'BUSINESS_BENCHMARK'))
export type QualityReport = z.infer<typeof qualityReportSchema>
export type QualityReports = z.infer<typeof qualityReportsSchema>
export type QualityReportSlot = z.infer<typeof slot>
