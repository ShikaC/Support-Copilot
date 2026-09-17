import { Tag } from 'antd'
import ReactECharts from 'echarts-for-react/esm/core'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useState } from 'react'
import type { Metrics, Ticket } from '../../types'
import { UnavailablePanel } from '../shared/presentation'
import { slaLabel, statusLabels } from '../shared/presentationData'
import { StatusStrip } from '../tickets/StatusStrip'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

export function OverviewView({ metrics, tickets }: { readonly metrics: Metrics | null; readonly tickets: readonly Ticket[] }) {
  const reducedMotion = useReducedMotion()
  if (!metrics) return <div className="view-enter"><StatusStrip metrics={null} /><UnavailablePanel title="运营指标暂不可用" description="工单列表仍可使用；指标服务恢复后重新加载页面即可查看趋势和质量数据。" /></div>
  const trendOption = {
    animation: !reducedMotion, animationDuration: reducedMotion ? 0 : 350, color: ['#1d8067', '#c4872c'], tooltip: { trigger: 'axis', borderWidth: 0, textStyle: { fontSize: 11 } },
    legend: { top: 8, right: 12, itemWidth: 10, itemHeight: 6, textStyle: { color: '#66706a', fontSize: 10 } },
    grid: { top: 48, right: 22, bottom: 28, left: 38 },
    xAxis: { type: 'category', boundaryGap: false, data: metrics.ticketTrend.map((item) => item.date), axisLine: { lineStyle: { color: '#dde1dc' } }, axisTick: { show: false }, axisLabel: { color: '#7c847f', fontSize: 10 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceeea' } }, axisLabel: { color: '#7c847f', fontSize: 10 } },
    series: [
      { name: '新建', type: 'line', smooth: 0.25, symbol: 'circle', symbolSize: 5, lineStyle: { width: 2 }, data: metrics.ticketTrend.map((item) => item.created) },
      { name: '已记录解决', type: 'line', smooth: 0.25, symbol: 'circle', symbolSize: 5, lineStyle: { width: 2 }, data: metrics.ticketTrend.map((item) => item.resolved) },
    ],
  }
  const categoryOption = {
    animation: !reducedMotion, animationDuration: reducedMotion ? 0 : 350, color: ['#397c68'], tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, borderWidth: 0 },
    grid: { top: 16, right: 30, bottom: 20, left: 78 },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceeea' } }, axisLabel: { color: '#7c847f', fontSize: 10 } },
    yAxis: { type: 'category', inverse: true, data: metrics.categoryDistribution.map((item) => item.category), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#59635d', fontSize: 10 } },
    series: [{ type: 'bar', barWidth: 10, itemStyle: { borderRadius: 2 }, data: metrics.categoryDistribution.map((item) => item.count) }],
  }
  return <div className="view-enter"><StatusStrip metrics={metrics} /><div className="dashboard-grid">
    <div><section className="dashboard-panel"><div className="panel-header"><div className="panel-heading"><h2 className="panel-title">工单趋势</h2><div className="panel-meta">最近 7 天 · UTC · 解决量从启用记录后统计</div></div><Tag>最近 7 天</Tag></div>
      <div className="chart-panel-body" aria-describedby="ticket-trend-data" data-reduced-motion={reducedMotion}>{metrics.ticketTrend.length > 0 ? <ReactECharts echarts={echarts} option={trendOption} style={{ height: '100%' }} /> : <UnavailablePanel title="趋势数据暂不可用" description="当前接口只返回工单快照，尚未提供可追溯的历史趋势数据。" />}</div>
      <div className="visually-hidden" id="ticket-trend-data"><table aria-label="工单趋势数据"><thead><tr><th>日期</th><th>新建</th><th>已记录解决</th></tr></thead><tbody>{metrics.ticketTrend.map((item) => <tr key={item.date}><th>{item.date}</th><td>{item.created}</td><td>{item.resolved}</td></tr>)}</tbody></table></div></section>
      <section className="dashboard-panel"><div className="panel-header"><div className="panel-heading"><h2 className="panel-title">近期高风险工单</h2><div className="panel-meta">已加载开放工单 · 按 SLA 截止时间排序</div></div></div>
        <div style={{ overflowX: 'auto' }}><table className="recent-ticket-table record-table"><thead><tr><th>工单</th><th>客户</th><th>状态</th><th className="numeric">SLA</th></tr></thead><tbody>{tickets.filter((ticket) => !['RESOLVED', 'CLOSED'].includes(ticket.status)).sort((a, b) => Date.parse(a.slaDeadline) - Date.parse(b.slaDeadline)).slice(0, 5).map((ticket) => <tr key={ticket.id}><td data-label="工单">{ticket.subject}</td><td data-label="客户">{ticket.customerCompany}</td><td data-label="状态">{statusLabels[ticket.status]}</td><td data-label="SLA" className="numeric">{slaLabel(ticket.slaDeadline)}</td></tr>)}</tbody></table></div>
      </section></div>
    <div><section className="dashboard-panel"><div className="panel-header"><div className="panel-heading"><h2 className="panel-title">类别分布</h2><div className="panel-meta">当前开放工单</div></div></div><div className="chart-panel-body" aria-describedby="category-distribution-data" data-reduced-motion={reducedMotion}><ReactECharts echarts={echarts} option={categoryOption} style={{ height: '100%' }} /></div>
      <div className="visually-hidden" id="category-distribution-data"><table aria-label="类别分布数据"><thead><tr><th>类别</th><th>工单数</th></tr></thead><tbody>{metrics.categoryDistribution.map((item) => <tr key={item.category}><th>{item.category}</th><td>{item.count}</td></tr>)}</tbody></table></div></section>
      <section className="dashboard-panel"><div className="panel-header"><div className="panel-heading"><h2 className="panel-title">辅助质量</h2><div className="panel-meta">当前评估基线</div></div></div><div className="quality-list">
        <QualityRow name="建议回复采纳率" context="编辑后采纳计入" value={metrics.suggestionAcceptanceRate == null ? '--' : `${(metrics.suggestionAcceptanceRate * 100).toFixed(1)}%`} />
        <QualityRow name="平均分析耗时" context={metrics.analysisLatency == null ? '暂无分析耗时记录' : `最近最多 1000 次 · p95 ${metrics.analysisLatency.p95Ms} ms`} value={metrics.analysisLatency == null ? '--' : `${(metrics.analysisLatency.averageMs / 1000).toFixed(2)}s`} />
        <QualityRow name="无证据安全率" context={metrics.evaluation == null ? '暂无评估报告' : '来自离线评估集'} value={metrics.evaluation == null ? '--' : `${(metrics.evaluation.noEvidenceSafetyRate * 100).toFixed(1)}%`} />
      </div></section></div>
  </div></div>
}

function useReducedMotion() {
  const query = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(query).matches)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const media = window.matchMedia(query)
    const update = (event: MediaQueryListEvent) => setReduced(event.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return reduced
}

function QualityRow({ name, context, value }: { readonly name: string; readonly context: string; readonly value: string }) {
  return <div className="quality-row"><div><div className="quality-name">{name}</div><div className="quality-context">{context}</div></div><span className="quality-value">{value}</span></div>
}
