import { Tag } from 'antd'
import type { Metrics } from '../../types'
import { UnavailablePanel } from '../shared/presentation'

export function LegacyQualityMetrics({ metrics, metricsError }: { readonly metrics: Metrics | null; readonly metricsError: boolean }) {
  if (metricsError) return <div className="view-enter"><UnavailablePanel title="质量指标请求失败" description="指标接口请求失败，当前页面没有可展示的质量数字。请检查 Java API 和本地服务日志。" /></div>
  if (!metrics?.evaluation) return <div className="view-enter"><UnavailablePanel title="质量指标暂不可用" description="当前没有收到可追溯的评估报告，因此不展示硬编码的质量数字。请配置可追溯的评估报告。" /></div>
  const evaluation = metrics.evaluation
  const retrievalLabel = evaluation.mode === 'live' ? '检索流程成功率' : `Hit@${evaluation.topK}`
  const citationLabel = evaluation.mode === 'live' ? '引用规则通过率' : '引用覆盖率'
  return <div className="view-enter"><section className="quality-panel">
    <div className="evaluation-disclosure"><Tag color={evaluation.mode === 'live' ? 'blue' : 'gold'}>{evaluation.mode === 'live' ? 'Live · 固定数据集评估' : 'Mock · 离线评估'}</Tag><span>以下数字来自 {evaluation.totalCases} 条评估案例，不代表生产客服效果。</span></div>
    <div className="quality-hero">
      <Metric label={retrievalLabel} value={`${(evaluation.hitRateAtK * 100).toFixed(1)}%`} note={evaluation.mode === 'live' ? '流程指标，不等于答案准确率' : '来自后端评估报告'} />
      <Metric label="MRR" value={evaluation.mrr.toFixed(3)} note={evaluation.mode === 'live' ? '流程指标，不等于答案准确率' : '来自后端评估报告'} />
      <Metric label="无证据安全率" value={`${(evaluation.noEvidenceSafetyRate * 100).toFixed(1)}%`} note="样本数见评估报告" />
      <Metric label={citationLabel} value={`${(evaluation.citationCoverage * 100).toFixed(1)}%`} note="校验规则见评估报告" />
    </div>
    <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">评估运行</h2><div className="panel-meta">{evaluation.datasetName} · {evaluation.totalCases} 条案例 · {evaluation.modelName}</div></div></div>
    <div className="evaluation-table-wrap" tabIndex={0} role="region" aria-label="评估结果表，可横向滚动"><table className="evaluation-table record-table"><thead><tr><th>评估集</th><th className="numeric">样本</th><th>配置</th><th className="numeric">{retrievalLabel}</th><th className="numeric">MRR</th><th className="numeric">p95</th><th>门禁</th></tr></thead><tbody><tr><td data-label="评估集">{evaluation.datasetName}</td><td data-label="样本" className="numeric">{evaluation.totalCases}</td><td data-label="配置">{evaluation.mode} · top {evaluation.topN}/{evaluation.topK}</td><td data-label={retrievalLabel} className="numeric">{(evaluation.hitRateAtK * 100).toFixed(1)}%</td><td data-label="MRR" className="numeric">{evaluation.mrr.toFixed(3)}</td><td data-label="p95" className="numeric">{evaluation.p95DurationMs} ms</td><td data-label="门禁"><Tag color={evaluation.passed ? 'green' : 'red'}>{evaluation.passed ? '通过' : `未通过 · ${evaluation.thresholdFailureCount} 项`}</Tag></td></tr></tbody></table></div>
  </section></div>
}

function Metric({ label, value, note }: { readonly label: string; readonly value: string; readonly note: string }) {
  return <div className="quality-hero-item"><span className="quality-hero-label">{label}</span><span className="quality-hero-value">{value}</span><span className="quality-hero-note">{note}</span></div>
}
