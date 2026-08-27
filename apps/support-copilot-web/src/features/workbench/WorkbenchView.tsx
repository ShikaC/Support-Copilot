import type { AnalysisReview, Metrics, Ticket } from '../../types'
import { AnalysisColumn } from '../analysis/AnalysisColumn'
import { TicketDetail } from '../tickets/TicketDetail'
import { TicketQueue } from '../tickets/TicketQueue'
import { StatusStrip } from '../tickets/StatusStrip'
import { UnavailablePanel } from '../shared/presentation'

type WorkbenchViewProps = {
  readonly tickets: readonly Ticket[]
  readonly selectedTicket: Ticket | null
  readonly metrics: Metrics | null
  readonly analyzing: boolean
  readonly onSelect: (ticketId: string) => void
  readonly onAnalyze: () => void
  readonly onReviewSaved: (review: AnalysisReview) => void
  readonly onAssign: () => void
  readonly onUnassign: () => void
  readonly assigneeUpdating: boolean
  readonly onToast: (message: string, kind?: 'success' | 'error') => void
}

export function WorkbenchView(props: WorkbenchViewProps) {
  const { tickets, selectedTicket, metrics } = props
  if (selectedTicket === null) return <div className="view-enter"><StatusStrip metrics={metrics} /><UnavailablePanel title="工单数据暂不可用" description="当前身份没有可显示的工单，请确认登录状态或稍后重试。" /></div>
  return <div className="view-enter"><StatusStrip metrics={metrics} /><div className="workspace">
    <TicketQueue tickets={tickets} selectedTicketId={selectedTicket.id} onSelect={props.onSelect} />
    <TicketDetail ticket={selectedTicket} analyzing={props.analyzing} onAnalyze={props.onAnalyze} onAssign={props.onAssign} onUnassign={props.onUnassign} assigneeUpdating={props.assigneeUpdating} />
    <AnalysisColumn ticket={selectedTicket} analyzing={props.analyzing} onAnalyze={props.onAnalyze} onReviewSaved={props.onReviewSaved} onToast={props.onToast} />
  </div></div>
}
