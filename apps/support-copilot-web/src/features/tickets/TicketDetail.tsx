import { Button, Spin, Tag } from 'antd'
import { Play, UserRound, UserRoundX } from 'lucide-react'
import type { Ticket } from '../../types'
import { categoryLabels, formatDate, formatTicketDescription, formatTime, slaLabel, statusColors, statusLabels } from '../shared/presentationData'

type TicketDetailProps = {
  readonly ticket: Ticket
  readonly analyzing: boolean
  readonly onAnalyze: () => void
  readonly onAssign: () => void
  readonly onUnassign: () => void
  readonly assigneeUpdating: boolean
}

export function TicketDetail(props: TicketDetailProps) {
  const { ticket, analyzing, onAnalyze, onAssign, onUnassign, assigneeUpdating } = props
  return <section className="workspace-column detail-column" aria-label="工单详情">
    <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">工单详情</h2><div className="panel-meta">更新于 {formatDate(ticket.updatedAt)}</div></div></div>
    <div className="detail-scroll">
      <div className="detail-meta-row"><Tag color={statusColors[ticket.status]}>{statusLabels[ticket.status]}</Tag><span className="ticket-no">{ticket.ticketNo}</span></div>
      <h2 className="ticket-detail-title">{ticket.subject}</h2>
      <div className="ticket-detail-company">{ticket.customerName} · {ticket.customerCompany}<span className="customer-tier">{ticket.customerTier}</span></div>
      <div className="detail-actions">
        <Button type="primary" icon={analyzing ? <Spin size="small" /> : <Play size={14} />} loading={analyzing} onClick={onAnalyze}>{ticket.latestAnalysis ? '重新分析' : '开始分析'}</Button>
        <Button icon={<UserRound size={14} />} loading={assigneeUpdating} disabled={assigneeUpdating} onClick={onAssign}>{ticket.assigneeName ? '重新分配' : '领取工单'}</Button>
        {ticket.assigneeName && <Button icon={<UserRoundX size={14} />} loading={assigneeUpdating} disabled={assigneeUpdating} onClick={onUnassign}>取消负责人</Button>}
      </div>
      <div className="detail-grid">
        <div><span className="detail-label">当前分类</span><span className="detail-value">{categoryLabels[ticket.category] ?? ticket.category}</span></div>
        <div><span className="detail-label">负责人</span><span className="detail-value">{ticket.assigneeName ?? '未分配'}</span></div>
        <div><span className="detail-label">来源渠道</span><span className="detail-value">{ticket.channel.replace('_', ' ')}</span></div>
        <div><span className="detail-label">SLA 剩余</span><span className="detail-value">{slaLabel(ticket.slaDeadline)}</span></div>
      </div>
      <div className="section-block"><h3 className="section-label">客户问题</h3><div className="message-body">{formatTicketDescription(ticket.description)}</div></div>
      <div className="section-block"><h3 className="section-label">处理记录</h3>
        {ticket.events.length === 0 ? <div className="timeline-item"><span className="timeline-dot" /><div><div className="timeline-label">工单已进入队列</div><div className="timeline-detail">等待客服处理</div></div><span className="timeline-time">{formatTime(ticket.createdAt)}</span></div> :
          <div className="timeline">{ticket.events.map((event) => <div className="timeline-item" key={event.id}><span className="timeline-dot" /><div><div className="timeline-label">{event.label}</div><div className="timeline-detail">{event.detail}</div></div><span className="timeline-time">{formatTime(event.createdAt)}</span></div>)}</div>}
      </div>
    </div>
  </section>
}
