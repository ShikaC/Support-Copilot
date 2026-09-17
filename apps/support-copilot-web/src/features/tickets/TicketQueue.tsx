import { useEffect, useMemo, useState } from 'react'
import { Button, Empty, Input, Segmented, Select } from 'antd'
import { ArrowDownWideNarrow, Plus, Search } from 'lucide-react'
import type { Ticket } from '../../types'
import { pendingTicketQuery, type TicketQueueQuery } from '../../services/ticketWorkspaceSchemas'
import { priorityLabels, secondsUntil, slaLabel, statusLabels } from '../shared/presentationData'
import { isTerminal } from './ticketLifecycle'

type TicketQueueProps = {
  readonly tickets: readonly Ticket[]; readonly selectedTicketId: string; readonly onSelect: (ticketId: string) => void
  readonly onCreate: () => void; readonly onQuery: (query: TicketQueueQuery) => void
  readonly nextCursor: string | null; readonly onLoadMore: () => void; readonly loading: boolean; readonly error: boolean
  readonly onRetry: () => void; readonly totalCount: number | null
}
export function TicketQueue(props: TicketQueueProps) {
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<string | number>('待处理')
  const [priority, setPriority] = useState('ALL')
  const [sort, setSort] = useState<NonNullable<TicketQueueQuery['sort']>>('NEWEST')
  const [assigneeMode, setAssigneeMode] = useState<'ALL' | 'UNASSIGNED' | 'NAMED'>('ALL')
  const [assigneeName, setAssigneeName] = useState('')
  const [debouncing, setDebouncing] = useState(false)
  const [interacted, setInteracted] = useState(false)
  const onQuery = props.onQuery
  const assignee = assigneeMode === 'UNASSIGNED' ? 'UNASSIGNED' : assigneeMode === 'NAMED' ? assigneeName.trim() : ''
  const preview = props.tickets.length > 0 && props.tickets.every((ticket) => ticket.version === undefined)
  const markChanged = () => { setInteracted(true); setDebouncing(true) }
  useEffect(() => {
    if (!interacted) return
    const timer = window.setTimeout(() => {
      onQuery({
        keyword: query.trim(), status: scope === '全部' ? '' : scope === '需升级' ? 'NEEDS_ESCALATION' : pendingTicketQuery.status,
        priority: priority === 'ALL' ? '' : priority, sort, assignee,
      })
      setDebouncing(false)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [query, scope, priority, sort, assignee, assigneeMode, assigneeName, interacted, onQuery])
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    const matches = props.tickets.filter((ticket) => {
      const scopeMatches = scope === '全部' || (scope === '待处理' && !isTerminal(ticket.status)) || (scope === '需升级' && ticket.status === 'NEEDS_ESCALATION')
      const assigneeMatches = !assignee || (assignee === 'UNASSIGNED' ? !ticket.assigneeName : ticket.assigneeName === assignee)
      return scopeMatches && assigneeMatches && (priority === 'ALL' || ticket.priority === priority) && (!normalized ||
        [ticket.ticketNo, ticket.subject, ticket.customerName, ticket.customerCompany, ticket.description].join(' ').toLowerCase().includes(normalized))
    })
    if (!preview) return matches
    const priorityRank = { URGENT: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }
    return matches.sort((a, b) => {
      const difference = sort === 'SLA' ? Date.parse(a.slaDeadline) - Date.parse(b.slaDeadline) : sort === 'PRIORITY' ? priorityRank[b.priority] - priorityRank[a.priority] : 0
      return difference || Date.parse(b.createdAt) - Date.parse(a.createdAt) || b.id.localeCompare(a.id)
    })
  }, [props.tickets, query, scope, priority, sort, assignee, preview])
  const syncing = props.loading || debouncing
  const count = syncing ? '…' : preview ? filtered.length : props.error ? '—' : props.totalCount ?? filtered.length
  const countLabel = syncing ? '正在同步筛选结果' : preview ? `本地预览 · ${filtered.length} 条` : props.error ? '筛选未完成 · 请重试' : props.totalCount === null ? `已加载 ${filtered.length} 条 · 总数暂不可用` : `已加载 ${filtered.length} / 共 ${props.totalCount} 条`
  return <section className="workspace-column queue-column" aria-label="工单队列">
    <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">工单队列</h2><span className="count-badge">{count}</span></div><button className="icon-button" type="button" aria-label="新建工单" onClick={props.onCreate}><Plus /></button></div>
    <div className="queue-controls"><Input aria-label="搜索工单" allowClear prefix={<Search size={15} />} placeholder="搜索编号、客户、标题或正文" maxLength={120} value={query} onChange={(event) => { markChanged(); setQuery(event.target.value) }} />
      <Segmented block options={['待处理', '需升级', '全部']} value={scope} onChange={(value) => { markChanged(); setScope(value) }} />
      <div className="queue-filter-row"><Select aria-label="按优先级筛选" value={priority} onChange={(value) => { markChanged(); setPriority(value) }} size="small" options={[{ value: 'ALL', label: '全部优先级' }, ...Object.entries(priorityLabels).map(([value, label]) => ({ value, label }))]} /><Select aria-label="队列排序" prefix={<ArrowDownWideNarrow size={13} />} value={sort} size="small" onChange={(value) => { markChanged(); setSort(value) }} options={[{ value: 'NEWEST', label: '最新创建' }, { value: 'SLA', label: 'SLA 最紧急' }, { value: 'PRIORITY', label: '优先级最高' }]} /></div>
      <Select aria-label="按负责人筛选" value={assigneeMode} size="small" onChange={(value) => { markChanged(); setAssigneeMode(value) }} options={[{ value: 'ALL', label: '全部负责人' }, { value: 'UNASSIGNED', label: '未分配负责人' }, { value: 'NAMED', label: '指定负责人' }]} />
      {assigneeMode === 'NAMED' && <Input aria-label="负责人姓名" allowClear maxLength={80} placeholder="输入完整负责人姓名" value={assigneeName} onChange={(event) => { markChanged(); setAssigneeName(event.target.value) }} />}
    </div>
    {props.loading && <div className="queue-loading" role="status">正在同步工单…</div>}
    {props.error && <div className="queue-error">队列同步失败 <button type="button" onClick={props.onRetry}>重试</button></div>}
    <div className="ticket-list">{filtered.length === 0 ? <div className="empty-queue"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={props.loading ? '正在加载' : '没有匹配的工单'} /></div> : filtered.map((ticket) => {
      const slaRisk = !isTerminal(ticket.status) && secondsUntil(ticket.slaDeadline) < 7200
      return <button className={`ticket-row ${ticket.id === props.selectedTicketId ? 'selected' : ''}`} aria-pressed={ticket.id === props.selectedTicketId} type="button" key={ticket.id} onClick={() => props.onSelect(ticket.id)}>
        <span className="ticket-row-top"><span className="ticket-no">{ticket.ticketNo}</span><span className="priority-label"><span className={`priority-dot ${ticket.priority}`} />{priorityLabels[ticket.priority]}</span></span>
        <span className="ticket-subject">{ticket.subject}</span><span className="ticket-preview">{ticket.description}</span>
        <span className="ticket-row-bottom"><span className="ticket-company"><span className="mini-avatar">{ticket.customerName.slice(0, 1)}</span>{ticket.customerCompany}</span><span className="queue-status">{statusLabels[ticket.status]}</span></span>
        <span className={`queue-sla ${slaRisk ? 'risk' : ''}`}>{isTerminal(ticket.status) ? '处理已结束' : slaLabel(ticket.slaDeadline)}</span>
      </button>
    })}</div>
    <div className="queue-footer"><span aria-live="polite">{countLabel}</span>{props.nextCursor && <Button block loading={props.loading} disabled={syncing || props.error} onClick={props.onLoadMore}>加载更多工单</Button>}</div>
  </section>
}
