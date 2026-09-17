import { Empty, Tabs, Tooltip } from 'antd'
import { Clock3, RefreshCw } from 'lucide-react'
import type { ApiClient } from '../../services/api'
import type { AnalysisReview, Ticket } from '../../types'
import { formatTime } from '../shared/presentationData'
import { EvidencePanel } from './EvidencePanel'
import { ReplyReview } from './ReplyReview'
import { WorkflowPanel } from './WorkflowPanel'

type AnalysisColumnProps = {
  readonly ticket: Ticket
  readonly client: ApiClient
  readonly analyzing: boolean
  readonly onAnalyze: () => void
  readonly onReviewSaved: (review: AnalysisReview) => void
  readonly onRefreshTicket: (ticketId: string) => Promise<void>
  readonly onToast: (message: string, kind?: 'success' | 'error') => void
}

export function AnalysisColumn(props: AnalysisColumnProps) {
  const { ticket, client, analyzing, onAnalyze, onReviewSaved, onRefreshTicket, onToast } = props
  const analysis = ticket.latestAnalysis
  if (analyzing) return <section className="workspace-column analysis-column" aria-label="AI 分析">
    <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">辅助分析</h2><div className="panel-meta">正在执行知识检索与风险检查</div></div></div>
    <div className="analysis-content"><div className="workflow-list">{['内容预处理', '工单理解', '知识检索', '回复生成', '风险检查'].map((name, index) => <div className="workflow-step" key={name}><span className={`step-icon ${index === 0 ? 'running' : ''}`}>{index === 0 ? <RefreshCw /> : <Clock3 />}</span><div><div className="step-name">{name}</div><div className="step-description">{index === 0 ? '正在处理当前工单内容' : '等待上一步完成'}</div></div><span className="step-duration">{index === 0 ? '运行中' : '等待'}</span></div>)}</div></div>
  </section>
  if (!analysis) return <section className="workspace-column analysis-column" aria-label="AI 分析">
    <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">辅助分析</h2><div className="panel-meta">尚未运行</div></div></div>
    <div className="analysis-content"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="运行分析后将在这里显示处理轨迹与知识证据" /></div>
  </section>
  return <section className="workspace-column analysis-column" aria-label="AI 分析">
    <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">辅助分析</h2><div className="panel-meta">{analysis.modelName} · {formatTime(analysis.createdAt)}</div></div>
      <Tooltip title="刷新分析结果"><button className="icon-button" type="button" aria-label="刷新分析结果" onClick={onAnalyze}><RefreshCw /></button></Tooltip>
    </div>
    <div className="analysis-scroll"><Tabs className="analysis-tabs" defaultActiveKey="workflow" items={[
      { key: 'workflow', label: '处理轨迹', children: <WorkflowPanel analysis={analysis} /> },
      { key: 'evidence', label: `知识依据 ${analysis.retrieval.hits.filter((hit) => hit.usedAsEvidence).length}`, children: <EvidencePanel analysis={analysis} /> },
      { key: 'reply', label: '回复建议', children: <ReplyReview ticket={ticket} analysis={analysis} client={client} onRefreshTicket={onRefreshTicket} onReviewSaved={onReviewSaved} onToast={onToast} /> },
    ]} /></div>
  </section>
}
