import assert from 'node:assert/strict';
import { isDeepStrictEqual } from 'node:util';
import { nearestRank } from '../benchmark/metrics.mjs';
import { outcome, countOutcomes, failures, assertUnique, metric } from './report-outcomes.mjs';

export function businessReport(input, sourceFiles) {
  const { trials, summary, manifest } = input;
  assert.equal(manifest.state, 'COMPLETE_UNREVIEWED');
  assert.equal(trials.length, manifest.planned);
  const rows = trials.map(trial => {
    const analysis = trial.stages.analyze;
    const body = analysis?.body;
    const persisted = trial.stages.history?.status === 200 && Array.isArray(trial.stages.history.body)
      && trial.stages.history.body.some(saved => isDeepStrictEqual(saved, body));
    assert.equal(persisted, trial.persisted, 'raw full readback differs from saved flag');
    const transportOk = trial.error === null && trial.stages.create.status === 201 && analysis?.status === 200;
    return {
      caseId: trial.case_id, concurrency: trial.concurrency, traceId: body?.traceId ?? null,
      reason: transportOk && persisted ? body?.fallbackReason : 'http_or_persistence_error',
      outcome: transportOk && persisted ? outcome({ status: body?.status, mode: body?.mode, reason: body?.fallbackReason }) : 'error',
      duration: trial.create_to_analysis_ms, apiCompleted: analysis?.status === 200, persisted,
    };
  });
  assertUnique(rows);
  const groups = summary.metrics.map(expected => {
    const group = rows.filter(row => row.concurrency === expected.concurrency);
    assert.equal(group.length, expected.n);
    const counts = countOutcomes(group);
    const p50Ms = nearestRank(group.map(row => row.duration), 0.5);
    const p95Ms = nearestRank(group.map(row => row.duration), 0.95);
    const apiCompleted = group.filter(row => row.apiCompleted).length;
    const persisted = group.filter(row => row.persisted).length;
    assert.equal(counts.normalLive, expected.live);
    assert.equal(counts.evidenceInsufficient, expected.evidence_insufficient);
    assert.equal(counts.timeout + counts.otherFallback, expected.dependency_or_other_fallback);
    assert.equal(counts.error, expected.http_or_persistence_errors);
    assert.equal(p50Ms, expected.create_to_analysis_p50_ms);
    assert.equal(p95Ms, expected.create_to_analysis_p95_ms);
    assert.equal(apiCompleted, expected.api_completed);
    assert.equal(persisted, expected.persisted);
    return { concurrency: expected.concurrency, total: group.length, ...counts, p50Ms, p95Ms, apiCompleted, persisted };
  });
  assert.deepEqual(groups.map(group => group.concurrency), manifest.concurrency);
  assert.equal(groups.reduce((n, group) => n + group.total, 0), rows.length);
  const distinctCaseCount = new Set(rows.map(row => row.caseId)).size;
  assert.equal(distinctCaseCount, summary.quality_distinct_cases);
  assert(groups.every(group => group.total === distinctCaseCount), 'each concurrency must use the same fixed cases');
  const n = rows.length;
  return {
    schemaVersion: 1, id: 'doc2dial-business-20260910-run-1', kind: 'BUSINESS_BENCHMARK',
    title: '公开文档业务链路基准', dataset: 'Doc2Dial v1.0.1 · 固定输入 32 题',
    generatedAt: manifest.finished_at, sourceFiles, sampleCount: n, distinctCaseCount, humanReviewedCount: 0,
    answerAccuracy: null, businessResolutionRate: null, timeSavedMinutes: null, cost: null,
    outcomes: countOutcomes(rows), groups, failures: failures(rows),
    metrics: [
      metric('api-completed', '分析接口完成率', rows.filter(row => row.apiCompleted).length / n, 'RATE', n, 'HTTP 200 包括 fallback，不是正常 AI 产出或回答成功率。'),
      metric('immediate-readback', '即时完整读回一致率', rows.filter(row => row.persisted).length / n, 'RATE', n, '逐条比较分析响应与 Java 历史完整对象；不代表答案正确。'),
    ],
    gateReasons: ['reference-inputs-need-audit', 'human-review-incomplete', 'provider-timeouts-observed'],
    limitations: [
      'Doc2Dial 是基于公开文档人工构建的对话，不是企业真实客服日志。',
      '96 次分析来自 32 个固定问题在 1/2/4 并发各运行一遍，不能视为 96 个独立质量样本。',
      '旧样本含寒暄、上下文缺失和 fuzzy 参考标注；指定文档命中、跨度覆盖和词语 F1 均不能称为回答准确率。',
      '并发组顺序固定且样本较少；本地 H2 实验不能证明生产容量或并发导致的因果变化。',
      '耗时从创建工单开始，到分析响应（Java 保存之后）；包含降级和超时，历史读回计时另算。p50/p95 使用 nearest-rank。',
      '重启读回历史证据只比较 id、traceId、mode 和回复文本，未保存完整重启响应；不能声称重启后全字段一致。',
      '人工审核、客户问题解决率、节省工时和实际费用未测得；本报告只呈现冻结实验，不会自动跟随当前运行状态变化。',
    ],
  };
}
