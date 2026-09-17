import { useState } from 'react'
import { Button, Tag } from 'antd'
import type { QualityReport } from '../../services/qualityReports'

type Failure = QualityReport['failures'][number]
const outcomes = { EVIDENCE_INSUFFICIENT: '证据不足', TIMEOUT: '模型超时', OTHER_FALLBACK: '其他降级', ERROR: '错误' } as const
const filters = ['ALL', 'EVIDENCE_INSUFFICIENT', 'TIMEOUT', 'OTHER_FALLBACK', 'ERROR'] as const

export function QualityFailures({ failures }: { readonly failures: readonly Failure[] }) {
  const [filter, setFilter] = useState<(typeof filters)[number]>('ALL')
  const filtered = failures.filter((failure) => filter === 'ALL' || failure.outcome === filter)
  return <details className="quality-failures"><summary tabIndex={0}>失败与降级明细 · {failures.length}</summary>
    <div className="detail-actions quality-failure-filters" role="group" aria-label="按运行结果筛选">{filters.map((value) => <Button key={value} type={filter === value ? 'primary' : 'default'} aria-label={value === 'ALL' ? '全部' : outcomes[value]} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'ALL' ? '全部' : outcomes[value]}</Button>)}<span role="status" className="panel-meta">显示 {filtered.length} / {failures.length} 条</span></div>
    <div className="evaluation-table-wrap" role="region" aria-label="失败与降级记录" tabIndex={0}>{filtered.length === 0 ? <p className="analysis-content panel-meta">该分类没有记录。</p> : <table className="evaluation-table record-table"><thead><tr><th>问题</th><th>并发</th><th>结果</th><th>原因</th><th>Trace ID</th></tr></thead><tbody>{filtered.map((failure) => <tr key={`${failure.caseId}:${failure.concurrency}`}><td data-label="问题">{failure.caseId}</td><td data-label="并发">{failure.concurrency ?? '未分组'}</td><td data-label="结果"><Tag color={failure.outcome === 'EVIDENCE_INSUFFICIENT' ? 'gold' : 'red'}>{outcomes[failure.outcome]}</Tag></td><td data-label="原因">{failure.reason}</td><td data-label="Trace ID"><code>{failure.traceId ?? '未记录'}</code></td></tr>)}</tbody></table>}</div>
  </details>
}
