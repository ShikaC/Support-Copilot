import { Tag } from 'antd'
import type { QualityReport } from '../../services/qualityReports'
import { QualityFailures } from './QualityFailures'

const outcomeFields = [
  ['normalLive', '正常模型产出'], ['evidenceInsufficient', '证据不足'], ['timeout', '模型超时'], ['otherFallback', '其他降级'], ['error', '错误'],
] as const

export function QualityReportPanel({ report }: { readonly report: QualityReport }) {
  return <section className="quality-panel quality-report" aria-label={report.title}>
    <header className="panel-header"><div className="panel-heading"><div className="panel-meta">{report.kind === 'BUSINESS_BENCHMARK' ? '完整业务链路 · 公开数据' : '模型回归 · 固定评估集'}</div><h2 className="panel-title">{report.title}</h2><div className="panel-meta">{report.dataset} · {report.distinctCaseCount} 个不同问题 / {report.sampleCount} 次运行</div></div><Tag color="gold">人工审核 {report.humanReviewedCount} / {report.sampleCount}</Tag></header>
    <div className="quality-hero quality-outcomes" aria-label="运行结果分布">{outcomeFields.map(([key, label]) => <div key={key} className={`quality-hero-item quality-outcome-${key}`}><span className="quality-hero-label">{label}</span><strong className="quality-hero-value">{report.outcomes[key]}<small className="panel-meta"> / {report.sampleCount}</small></strong></div>)}</div>
    <div className="evaluation-disclosure quality-conclusion"><div><h3 className="quality-hero-label">回答准确率</h3><strong className="panel-title">尚未测得</strong></div><p>正常模型产出仅表示模型完成生成。人工审核、问题解决率、节省工时与成本仍需独立证据；HTTP 200 和保存成功不能代替回答成功。</p></div>
    {report.metrics.length > 0 && <dl className="quality-hero quality-report-metrics">{report.metrics.map((metric) => <div key={metric.id} className="quality-hero-item"><dt className="quality-hero-label">{metric.label}</dt><dd><span className="quality-hero-value">{formatMetric(metric.value, metric.unit)}</span><p className="panel-meta">{metric.description}{metric.denominator !== null && ` · 分母 ${metric.denominator}`}</p></dd></div>)}</dl>}
    {report.groups.length > 0 && <ConcurrencyResults report={report} />}
    <QualityFailures failures={report.failures} />
    <div className="analysis-content quality-report-boundary"><h3 className="panel-title">结论边界</h3><ul>{report.gateReasons.map((reason) => <li key={`gate-${reason}`} title={reason}>{gateReasonLabel(reason)}</li>)}{report.limitations.map((limitation) => <li key={`limit-${limitation}`}>{limitation}</li>)}</ul></div>
    <details className="quality-source"><summary tabIndex={0}>来源与校验摘要 · {report.sourceFiles.length} 个文件</summary><p>以下为导出报告声明的原始来源摘要；接口校验配置的导出报告摘要，不重新读取原始实验文件。<br />报告时间 {report.generatedAt} · 报告编号 <code>{report.id}</code></p><ul>{report.sourceFiles.map((source) => <li key={source.name}><span>{source.name}</span><code>SHA-256 {source.sha256}</code></li>)}</ul></details>
  </section>
}

function ConcurrencyResults({ report }: { readonly report: QualityReport }) {
  return <div className="quality-concurrency"><div className="panel-header"><div className="panel-heading"><h3 className="panel-title">并发与处理耗时</h3><p className="panel-meta">工单创建至分析响应耗时，含降级与保存；历史读回耗时单独计量。正常模型产出单独计数。</p></div></div>
    <div className="evaluation-table-wrap" tabIndex={0} role="region" aria-label="并发运行结果"><table className="evaluation-table record-table"><thead><tr><th>并发</th><th>正常 / 总数</th><th>证据不足</th><th>超时</th><th>其他降级 / 错误</th><th>p50 / p95</th><th>API 完成 / 保存</th></tr></thead><tbody>{report.groups.map((group) => <tr key={group.concurrency}>
      <td data-label="并发">{group.concurrency}</td><td data-label="正常 / 总数">{group.normalLive} / {group.total}</td><td data-label="证据不足">{group.evidenceInsufficient}</td><td data-label="超时">{group.timeout}</td><td data-label="降级 / 错误">{group.otherFallback} / {group.error}</td><td data-label="p50 / p95">{seconds(group.p50Ms)} / {seconds(group.p95Ms)}</td><td data-label="完成 / 保存">{group.apiCompleted} / {group.persisted}</td>
    </tr>)}</tbody></table></div>
  </div>
}

function seconds(value: number): string { return `${(value / 1000).toFixed(2)} s` }
function formatMetric(value: number | null, unit: QualityReport['metrics'][number]['unit']): string {
  if (value === null) return '未测得'
  switch (unit) {
    case 'RATE': return `${(value * 100).toFixed(1)}%`
    case 'MS': return seconds(value)
    case 'NUMBER': return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
    default: return unit
  }
}

function gateReasonLabel(reason: string): string {
  switch (reason) {
    case 'machine-gate-failed': return '自动规则检查未通过，请查看失败案例与指标。'
    case 'human-review-incomplete': return '人工审核尚未完成，当前不能形成回答准确率结论。'
    case 'reference-inputs-need-audit': return '评测输入与参考依据需要审计，当前分数不能代表回答准确率。'
    case 'provider-timeouts-observed': return '已观察到模型服务超时，需要排查稳定性与超时预算。'
    default: return `未知门禁代码：${reason}`
  }
}
