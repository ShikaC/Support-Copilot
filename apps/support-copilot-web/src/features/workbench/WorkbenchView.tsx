import { lazy, Suspense, useState, useEffect } from 'react'
import { Button } from 'antd'
import type { AnalysisReview, Metrics, Ticket } from '../../types'
import type { ApiClient, TicketUpdate } from '../../services/api'
import type { CreateTicketInput, TicketQueueQuery } from '../../services/ticketWorkspaceSchemas'
import { AnalysisColumn } from '../analysis/AnalysisColumn'
import { TicketDetail } from '../tickets/TicketDetail'
import { TicketQueue } from '../tickets/TicketQueue'
import { StatusStrip } from '../tickets/StatusStrip'
import { UnavailablePanel } from '../shared/presentation'

type WorkbenchViewProps = {
  readonly tickets: readonly Ticket[]; readonly selectedTicket: Ticket | null; readonly client: ApiClient
  readonly metrics: Metrics | null; readonly analyzing: boolean; readonly onSelect: (ticketId: string) => void
  readonly onAnalyze: () => void; readonly onReviewSaved: (review: AnalysisReview) => void
  readonly onRefreshTicket: (ticketId: string) => Promise<void>; readonly onAssign: () => void
  readonly onUnassign: () => void; readonly assigneeUpdating: boolean
  readonly onToast: (message: string, kind?: 'success' | 'error') => void
  readonly onCreate: (input: CreateTicketInput) => Promise<unknown>
  readonly onUpdate: (update: TicketUpdate) => Promise<boolean>; readonly updating: boolean
  readonly totalCount: number | null; readonly onQuery: (query: TicketQueueQuery) => void; readonly nextCursor: string | null
  readonly onLoadMore: () => void; readonly loading: boolean; readonly queueError: boolean; readonly onRetry: () => void
}
export function WorkbenchView(props: WorkbenchViewProps) {
  const { tickets, selectedTicket, metrics } = props
  const [CreateTicketDialog] = useState(() => lazy(() => import('../tickets/CreateTicketDialog').then((module) => ({ default: module.CreateTicketDialog }))))
  const [creating, setCreating] = useState(false)
  const [mobileDetail, setMobileDetail] = useState(true)
  useEffect(() => { setMobileDetail(true) }, [selectedTicket?.id])
  const [queueRevision, setQueueRevision] = useState(0)
  return <div className="view-enter workbench-view"><StatusStrip metrics={metrics} />
    <div className="workbench-toolbar"><div><span className="workspace-eyebrow">客户服务 / 收件箱</span><h2>每一个问题，都有下一步。</h2></div><div><Button onClick={props.onRetry} loading={props.loading}>刷新队列</Button><Button type="primary" onClick={() => setCreating(true)}>＋ 新建工单</Button></div></div>
    <div className={`workspace ${mobileDetail ? 'show-detail' : ''}`}>
      <TicketQueue totalCount={props.totalCount} key={queueRevision} tickets={tickets} selectedTicketId={selectedTicket?.id ?? ''} onSelect={(id) => { props.onSelect(id); setMobileDetail(true) }} onCreate={() => setCreating(true)} onQuery={props.onQuery} nextCursor={props.nextCursor} onLoadMore={props.onLoadMore} loading={props.loading} error={props.queueError} onRetry={props.onRetry} />
      {selectedTicket ? <><TicketDetail ticket={selectedTicket} analyzing={props.analyzing} onAnalyze={props.onAnalyze} onAssign={props.onAssign} onUnassign={props.onUnassign} assigneeUpdating={props.assigneeUpdating} client={props.client} onUpdate={props.onUpdate} updating={props.updating} onRefresh={props.onRefreshTicket} onBack={() => setMobileDetail(false)} />
      <AnalysisColumn ticket={selectedTicket} client={props.client} analyzing={props.analyzing} onAnalyze={props.onAnalyze} onReviewSaved={props.onReviewSaved} onRefreshTicket={props.onRefreshTicket} onToast={props.onToast} /></>
      : <div className="workspace-empty"><UnavailablePanel title={props.loading ? '正在读取工单' : '工单数据暂不可用'} description="创建工单后，即可开始分派、智能分析与人工审核。" /><Button type="primary" onClick={() => setCreating(true)}>新建工单</Button></div>}
    </div>
    {creating && <Suspense fallback={null}><CreateTicketDialog onClose={() => setCreating(false)} onCreate={async (input) => { await props.onCreate(input); setQueueRevision((value) => value + 1); setMobileDetail(true) }} /></Suspense>}
  </div>
}
