import { useEffect, useState } from 'react'
import { Alert, Button, Input, Modal, Spin } from 'antd'
import { ArrowUpRight, Search } from 'lucide-react'
import type { Ticket } from '../types'
import type { ApiClient } from '../services/api'

export type WorkspaceView = 'workbench' | 'overview' | 'knowledge' | 'audit' | 'quality'
const destinations: ReadonlyArray<{ readonly key: WorkspaceView; readonly label: string }> = [
  { key: 'workbench', label: '工单工作台' }, { key: 'overview', label: '运营概览' },
  { key: 'knowledge', label: '知识库' }, { key: 'audit', label: '审计记录' }, { key: 'quality', label: '质量评估' },
]
type Props = { readonly client: ApiClient; readonly onClose: () => void; readonly onNavigate: (view: WorkspaceView) => void; readonly tickets: readonly Ticket[]; readonly onSelect: (ticket: Ticket) => void }
export function CommandPalette({ client, onClose, onNavigate, tickets, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<{ readonly query: string; readonly tickets: readonly Ticket[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const normalized = query.trim()
  useEffect(() => {
    if (!normalized) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void client.fetchTicketPage({ keyword: normalized, limit: '8' }, { signal: controller.signal }).then((page) => {
        if (!controller.signal.aborted) setResult({ query: normalized, tickets: page.items })
      }).catch(() => { if (!controller.signal.aborted) setError('搜索暂不可用，请重试。') })
    }, 250)
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [client, normalized, attempt])
  const pending = Boolean(normalized) && result?.query !== normalized && !error
  const matches = normalized ? (result?.query === normalized ? result.tickets : []) : tickets.slice(0, 8)
  const navigation = destinations.filter((item) => item.label.includes(normalized))
  return <Modal open title="快速查找" footer={null} onCancel={onClose} width={580}>
    <Input autoFocus prefix={<Search size={17} />} size="large" aria-label="快速查找工单或页面" placeholder="搜索全部工单、客户或页面…" value={query} onChange={(event) => { setQuery(event.target.value); setError(null); setResult(null) }} />
    <div className="command-results">{navigation.length > 0 && <p className="section-label">前往页面</p>}{navigation.map((item) => <button type="button" key={item.key} onClick={() => { onNavigate(item.key); onClose() }}><span>{item.label}</span><ArrowUpRight size={14} /></button>)}
      <p className="section-label">{normalized ? '全部工单 · 最多显示 8 条匹配结果' : '当前已加载工单'}</p>
      <div aria-live="polite">{pending && <Spin tip="正在搜索全部工单"><div style={{ minHeight: 64 }} /></Spin>}{error && <Alert type="error" title={error} action={<Button size="small" onClick={() => { setError(null); setAttempt((value) => value + 1) }}>重试</Button>} />}</div>
      {matches.map((ticket) => <button type="button" key={ticket.id} onClick={() => { onNavigate('workbench'); onSelect(ticket); onClose() }}><span><strong>{ticket.subject}</strong><small>{ticket.ticketNo} · {ticket.customerCompany}</small></span><ArrowUpRight size={14} /></button>)}
      {!pending && !error && matches.length === 0 && <p className="field-hint">没有匹配工单</p>}
    </div><div className="command-hint"><span>Tab 切换 · Enter 打开</span><kbd>Esc 关闭</kbd></div>
  </Modal>
}
