import assert from 'node:assert/strict';
import { outcome, countOutcomes, failures, assertUnique, metric } from './report-outcomes.mjs';

export function liveReport(raw, sourceFiles) {
  assert.equal(raw.report_kind, 'live-evaluation');
  assert.equal(raw.run.mode, 'live');
  const rows = raw.cases.map(item => ({
    caseId: item.case_id, concurrency: null, reason: item.fallback_reason, traceId: item.trace_id,
    outcome: outcome({ status: item.status, mode: item.mode, reason: item.fallback_reason }),
  }));
  assertUnique(rows);
  const summary = raw.summary;
  assert.equal(rows.length, summary.total_cases);
  const outcomes = countOutcomes(rows);
  assert.equal(outcomes.normalLive, summary.succeeded_cases, 'normal live summary mismatch');
  assert.equal(rows.length - outcomes.normalLive - outcomes.error, summary.fallback_count);
  // This adapter supports the frozen, unreviewed baseline only. New human review
  // requires a separate authenticated review import, not a counter supplied by AI.
  assert.equal(summary.human_reviewed_count, 0, 'human review import is not supported');
  assert(raw.cases.every(item => item.human_review.factual_support === 'NOT_REVIEWED'
    && item.human_review.reviewer === null && item.human_review.reviewed_at === null));
  assert.equal(summary.publishable, false);
  const n = rows.length;
  for (const [flag, count, rate] of [
    ['retrieval_success', 'retrieval_success_count', 'retrieval_success_rate'],
    ['citation_valid', 'citation_valid_count', 'citation_valid_rate'],
  ]) {
    assert.equal(raw.cases.filter(item => item[flag] === true).length, summary[count]);
    assert.equal(summary[count] / n, summary[rate]);
  }
  return {
    schemaVersion: 1, id: raw.run.run_id, kind: 'LIVE_EVALUATION', title: '合成案例回归评估',
    dataset: `${raw.run.dataset_id}@${raw.run.dataset_version}`, generatedAt: raw.run.timestamp,
    sourceFiles, sampleCount: n, distinctCaseCount: n, humanReviewedCount: 0,
    answerAccuracy: null, businessResolutionRate: null, timeSavedMinutes: null, cost: null,
    outcomes, groups: [], failures: failures(rows),
    metrics: [
      metric('retrieval-process', '检索流程成功率', summary.retrieval_success_rate, 'RATE', n, '按固定案例的检索检查计数；不是指定文档 Hit@K 或回答准确率。'),
      metric('citation-rule', '引用规则通过率', summary.citation_valid_rate, 'RATE', n, '机器检查引用是否符合案例规则；预期拒答也可能通过，不证明回答事实全部正确。'),
      metric('latency-p95', '分析耗时 p95', summary.p95_latency_ms, 'MS', n, 'Python 评估入口计时，含降级与超时；不含 Java 保存或浏览器。nearest-rank。'),
    ],
    gateReasons: [...summary.gate_reasons, 'human-review-incomplete'],
    limitations: [
      `使用 ${raw.provenance.chat_model} · ${raw.run.prompt_version}；模型结构产出不等于回答正确。`,
      '合成回归案例用于开发诊断，不是独立真实客户测试；正常 live 不代表已人工认可。',
      '证据不足可属于预期安全拒答；它与依赖超时分别显示，均不计入正常 live 产出。',
      '人工事实审核未完成，回答准确率、问题解决率、节省工时与实际费用均未测得。',
    ],
  };
}
