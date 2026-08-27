import { AlertTriangle, CircleGauge, Clock3, Inbox } from 'lucide-react'
import type { Metrics } from '../../types'

export function StatusStrip({ metrics }: { readonly metrics: Metrics | null }) {
  const items = [
    { label: '待处理工单', value: metrics?.summary.openTickets ?? '--', delta: metrics ? '当前 H2 快照' : '指标暂不可用', icon: Inbox, tone: '' },
    { label: '紧急优先级', value: metrics?.summary.urgentTickets ?? '--', delta: metrics ? '当前工单快照' : '指标暂不可用', icon: AlertTriangle, tone: 'danger' },
    { label: 'SLA 风险', value: metrics?.summary.slaRiskTickets ?? '--', delta: metrics ? '按优先级计算' : '指标暂不可用', icon: Clock3, tone: 'warning' },
    {
      label: '分析成功率',
      value: metrics?.summary.analysisSuccessRate == null ? '--' : `${(metrics.summary.analysisSuccessRate * 100).toFixed(1)}%`,
      delta: metrics?.summary.analysisSuccessRate == null ? '暂无分析记录' : '来自分析记录',
      icon: CircleGauge, tone: 'neutral',
    },
  ]
  return <section className="status-strip" aria-label="队列状态">
    {items.map((item) => {
      const Icon = item.icon
      return <div className="status-metric" key={item.label}>
        <span className={`metric-icon ${item.tone}`}><Icon aria-hidden="true" /></span>
        <span><span className="metric-label">{item.label}</span>
          <span className={`metric-value ${metrics ? '' : 'metric-value-unavailable'}`}>{item.value}<span className="metric-delta">{item.delta}</span></span>
        </span>
      </div>
    })}
  </section>
}
