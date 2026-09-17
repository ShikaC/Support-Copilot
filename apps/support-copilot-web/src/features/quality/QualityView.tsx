import { useEffect, useState } from 'react'
import { Button, Spin } from 'antd'
import { ApiError, ApiRequestError, getQualityReports, type ApiClient } from '../../services/api'
import type { QualityReports, QualityReportSlot } from '../../services/qualityReports'
import type { Metrics } from '../../types'
import { UnavailablePanel } from '../shared/presentation'
import { LegacyQualityMetrics } from './LegacyQualityMetrics'
import { QualityReportPanel } from './QualityReportPanel'

type ReportState = { readonly kind: 'loading' } | { readonly kind: 'ready'; readonly data: QualityReports } | { readonly kind: 'error'; readonly message: string }

const defaultReportClient = { getQualityReports: ({ signal }: { readonly signal?: AbortSignal } = {}) => getQualityReports(signal) }

export function QualityView({ metrics, metricsError, client = defaultReportClient }: { readonly metrics: Metrics | null; readonly metricsError: boolean; readonly client?: Pick<ApiClient, 'getQualityReports'> }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<ReportState>({ kind: 'loading' })
  useEffect(() => {
    const controller = new AbortController()
    client.getQualityReports({ signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted) setState({ kind: 'ready', data })
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return
      const message = error instanceof ApiError ? error.message : error instanceof ApiRequestError ? error.message : '报告响应无法读取，请检查服务与报告配置。'
      setState({ kind: 'error', message })
    })
    return () => controller.abort()
  }, [attempt, client])

  const retry = () => { setState({ kind: 'loading' }); setAttempt((value) => value + 1) }
  return <div className="view-enter quality-center">
    <div className="panel-header quality-center-heading"><div><h1 className="page-title">质量证据</h1><p className="panel-meta">分别查看模型回归与完整业务链路。流程完成、规则通过与回答正确是不同的结论。</p></div><Button onClick={retry} loading={state.kind === 'loading'}>刷新报告</Button></div>
    {state.kind === 'loading' && <section className="quality-panel data-loading" role="status"><Spin /><span>正在校验并加载评估报告</span></section>}
    {state.kind === 'error' && <section className="quality-panel"><UnavailablePanel title="评估报告请求失败" description={state.message} /><div className="analysis-content"><Button onClick={retry}>重试加载报告</Button></div></section>}
    {state.kind === 'ready' && <><ReportSlot title="模型回归评估" slot={state.data.liveEvaluation} /><ReportSlot title="完整业务基准" slot={state.data.businessBenchmark} /></>}
    {(state.kind === 'ready' && state.data.liveEvaluation.status === 'NOT_CONFIGURED') && <LegacyQualityMetrics metrics={metrics} metricsError={metricsError} />}
  </div>
}

function ReportSlot({ title, slot }: { readonly title: string; readonly slot: QualityReportSlot }) {
  switch (slot.status) {
    case 'AVAILABLE': return <QualityReportPanel report={slot.report} />
    case 'NOT_CONFIGURED': return <UnavailablePanel title={`${title}尚未配置`} description="服务尚未配置该报告及摘要。其他报告可独立查看。" />
    case 'MISSING': return <UnavailablePanel title={`${title}文件不可用`} description="已配置的报告暂时无法读取，请检查报告文件。" />
    case 'INVALID': return <UnavailablePanel title="报告校验失败" description={`${title}未通过摘要或数据一致性检查，因此不展示其中数字。`} />
    default: return slot
  }
}
