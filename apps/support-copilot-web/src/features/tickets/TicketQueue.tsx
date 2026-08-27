import { useMemo, useState } from 'react'
import { Empty, Input, Segmented, Select } from 'antd'
import { Search } from 'lucide-react'
import type { Ticket } from '../../types'
import { priorityLabels, secondsUntil, slaLabel } from '../shared/presentation'

type TicketQueueProps = {
  readonly tickets: readonly Ticket[]
  readonly selectedTicketId: string
  readonly onSelect: (ticketId: string) => void
}

export function TicketQueue({ tickets, selectedTicketId, onSelect }: TicketQueueProps) {
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<string | number>('待处理')
  const [priority, setPriority] = useState('ALL')
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return tickets.filter((ticket) => {
      const scopeMatches = scope === '全部' ||
        (scope === '待处理' && !['RESOLVED', 'CLOSED'].includes(ticket.status)) ||
        (scope === '需升级' && ticket.status === 'NEEDS_ESCALATION')
      const priorityMatches = priority === 'ALL' || ticket.priority === priority
      const queryMatches = normalized.length === 0 ||
        [ticket.ticketNo, ticket.subject, ticket.customerName, ticket.customerCompany]
          .join(' ').toLowerCase().includes(normalized)
      return scopeMatches && priorityMatches && queryMatches
    })
  }, [priority, query, scope, tickets])

  return <section className="workspace-column queue-column" aria-label="工单队列">
    <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">工单队列</h2><div className="panel-meta">{filtered.length} 条匹配结果</div></div></div>
    <div className="queue-controls">
      <Input allowClear prefix={<Search size={14} />} placeholder="搜索编号、客户或标题" value={query} onChange={(event) => setQuery(event.target.value)} />
      <div className="queue-filter-row">
        <Segmented block options={['待处理', '需升级', '全部']} size="small" value={scope} onChange={setScope} />
        <Select aria-label="按优先级筛选" value={priority} onChange={setPriority} size="small" options={[
          { value: 'ALL', label: '全部优先级' }, { value: 'URGENT', label: '紧急' },
          { value: 'HIGH', label: '高' }, { value: 'MEDIUM', label: '中' }, { value: 'LOW', label: '低' },
        ]} />
      </div>
    </div>
    <div className="ticket-list">
      {filtered.length === 0 ? <div className="empty-queue"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的工单" /></div> : filtered.map((ticket) => {
        const slaRisk = secondsUntil(ticket.slaDeadline) < 2 * 3600
        return <button className={`ticket-row ${ticket.id === selectedTicketId ? 'selected' : ''}`} type="button" key={ticket.id} onClick={() => onSelect(ticket.id)}>
          <span className="ticket-row-top"><span className="ticket-no">{ticket.ticketNo}</span><span className="priority-label"><span className={`priority-dot ${ticket.priority}`} />{priorityLabels[ticket.priority]}</span></span>
          <span className="ticket-subject">{ticket.subject}</span>
          <span className="ticket-row-bottom"><span className="ticket-company">{ticket.customerCompany}</span><span className={`sla-time ${slaRisk ? 'risk' : ''}`}>{slaLabel(ticket.slaDeadline)}</span></span>
        </button>
      })}
    </div>
  </section>
}
