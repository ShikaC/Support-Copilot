import { lazy, Suspense, useState } from 'react'
import { Button, Popconfirm, Tag } from 'antd'
import { ArrowLeft, ArrowRight, BadgeCheck, CircleCheck, Mail, Pencil, Play, UserRound, UserRoundX } from 'lucide-react'
import type { Ticket } from '../../types'
import type { ApiClient, TicketUpdate } from '../../services/api'
import { categoryLabels, formatDate, formatTicketDescription, formatTime, slaLabel, statusColors, statusLabels } from '../shared/presentationData'
import { TicketNotes } from './TicketNotes'
import { isTerminal, manualTransitions, transitionLabels } from './ticketLifecycle'

type TicketDetailProps = {
  readonly ticket: Ticket; readonly analyzing: boolean; readonly onAnalyze: () => void
  readonly onAssign: () => void; readonly onUnassign: () => void; readonly assigneeUpdating: boolean
  readonly client: ApiClient; readonly onUpdate: (update: TicketUpdate) => Promise<boolean>
  readonly updating: boolean; readonly onRefresh: (id: string) => Promise<void>; readonly onBack: () => void
}
const channels: Readonly<Record<string, string>> = { EMAIL: '邮件', WEB_FORM: '网页表单', CHAT: '在线会话', PHONE: '电话' }
const tiers: Readonly<Record<string, string>> = { STANDARD: '标准客户', PREMIUM: '专业客户', ENTERPRISE: '企业客户' }
export function TicketDetail(props: TicketDetailProps) {
  const { ticket, analyzing, onAnalyze, onAssign, onUnassign, assigneeUpdating } = props
  const [{ EditTicketDialog, TicketActivity }] = useState(() => ({
    EditTicketDialog: lazy(() => import('./EditTicketDialog').then((module) => ({ default: module.EditTicketDialog }))),
    TicketActivity: lazy(() => import('./TicketActivity').then((module) => ({ default: module.TicketActivity }))),
  }))
  const [noteRevision, setNoteRevision] = useState(0)
  const [editing, setEditing] = useState(false)
  const terminal = isTerminal(ticket.status)
  return <section className="workspace-column detail-column" aria-label="工单详情">
    <div className="panel-header detail-panel-header"><div className="panel-heading"><button className="mobile-back icon-button" type="button" onClick={props.onBack} aria-label="返回工单队列"><ArrowLeft /></button><h2 className="panel-title">工单详情</h2><span className="panel-meta detail-ticket-id">{ticket.ticketNo}</span></div><Button type="text" size="small" icon={<Pencil size={14} />} onClick={() => setEditing(true)} disabled={terminal || analyzing || props.updating}>编辑属性</Button></div>
    <div className="detail-scroll">
      <div className="detail-meta-row"><Tag color={statusColors[ticket.status]}>{statusLabels[ticket.status]}</Tag><span className="detail-updated">更新于 {formatDate(ticket.updatedAt)}</span></div>
      <h2 className="ticket-detail-title">{ticket.subject}</h2>
      <div className="customer-identity"><span className="customer-avatar">{ticket.customerName.slice(0, 1)}</span><div><strong>{ticket.customerName}</strong><span>{ticket.customerCompany}</span></div><span className="customer-tier"><BadgeCheck size={13} /> {tiers[ticket.customerTier] ?? ticket.customerTier}</span></div>
      <div className="detail-grid">
        <div><span className="detail-label">业务分类</span><span className="detail-value">{categoryLabels[ticket.category] ?? ticket.category}</span></div>
        <div><span className="detail-label">负责人</span><span className="detail-value">{ticket.assigneeName ?? '未分配'}</span></div>
        <div><span className="detail-label">来源渠道</span><span className="detail-value">{channels[ticket.channel] ?? ticket.channel}</span></div>
        <div><span className="detail-label">服务时限</span><span className="detail-value">{terminal ? '处理已结束' : slaLabel(ticket.slaDeadline)}</span></div>
      </div>
      <section className="section-block customer-message"><h3 className="section-label"><Mail size={14} /> 客户问题 <time>{formatTime(ticket.createdAt)}</time></h3><div className="message-body">{formatTicketDescription(ticket.description)}</div></section>
      <div className="detail-actions">
        <Button type="primary" icon={<Play size={14} />} loading={analyzing} disabled={terminal || props.updating} onClick={onAnalyze}>{ticket.latestAnalysis ? '重新分析' : '开始分析'}</Button>
        <Button icon={<UserRound size={14} />} loading={assigneeUpdating} disabled={terminal || assigneeUpdating} onClick={onAssign}>{ticket.assigneeName ? '重新分配' : '领取工单'}</Button>
        {ticket.assigneeName && <Button icon={<UserRoundX size={14} />} loading={assigneeUpdating} disabled={terminal || assigneeUpdating} onClick={onUnassign}>取消负责人</Button>}
      </div>
      <div className="lifecycle-bar"><div><span className="section-label">下一步</span><p>{terminal ? '该工单已完成处理' : '由人工确认处理进度'}</p></div><div className="lifecycle-actions">{manualTransitions[ticket.status].map((status) => status === 'RESOLVED' || status === 'CLOSED'
        ? <Popconfirm key={status} title={status === 'RESOLVED' ? '确认客户问题已解决？' : '确认关闭工单？'} description={status === 'RESOLVED' ? '请先记录处理结论。AI 审核本身不会解决工单。' : '关闭后不能继续修改或分析。'} onConfirm={() => props.onUpdate({ status })} okText="确认" cancelText="取消"><Button icon={<CircleCheck size={14} />} loading={props.updating} disabled={analyzing}>{transitionLabels[status]}</Button></Popconfirm>
        : <Button key={status} icon={<ArrowRight size={14} />} loading={props.updating} disabled={analyzing} onClick={() => props.onUpdate({ status })}>{transitionLabels[status]}</Button>)}</div></div>
      <TicketNotes key={ticket.id} ticket={ticket} client={props.client} onRefresh={props.onRefresh} onSaved={() => setNoteRevision((value) => value + 1)} />
      <Suspense fallback={<p className="field-hint" role="status">正在加载处理记录…</p>}><TicketActivity key={`${ticket.id}:${noteRevision}`} ticket={ticket} client={props.client} /></Suspense>
    </div>
    {editing && <Suspense fallback={null}><EditTicketDialog key={ticket.id} ticket={ticket} onClose={() => setEditing(false)} onSave={props.onUpdate} /></Suspense>}
  </section>
}
