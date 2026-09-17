import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from 'antd'
import { History, RefreshCw } from 'lucide-react'
import { ApiContractError, ApiError, ApiRequestError, type ApiClient } from '../../services/api'
import type { TicketActivityPage } from '../../services/ticketWorkspaceSchemas'
import type { Ticket } from '../../types'

const activityDate = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

type ActivityClient = Pick<ApiClient, 'fetchTicketActivity'>
type Props = { readonly ticket: Ticket; readonly client: ActivityClient }
type HistoryProps = { readonly ticketId: string; readonly persisted: boolean; readonly client: ActivityClient }
type LoadFailure = { readonly message: string; readonly cursor: string | undefined }

export function TicketActivity({ ticket, client }: Props) {
  const revision = [ticket.id, ticket.version, ticket.latestAnalysis?.id, ticket.latestReview?.id].join(':')
  return <ActivityHistory key={revision} ticketId={ticket.id} persisted={ticket.version !== undefined} client={client} />
}

function ActivityHistory({ ticketId, persisted, client }: HistoryProps) {
  const [items, setItems] = useState<TicketActivityPage['items']>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(persisted)
  const [failure, setFailure] = useState<LoadFailure | null>(null)
  const [unexpectedFailure, setUnexpectedFailure] = useState<Error | null>(null)
  const activeRequest = useRef<AbortController | null>(null)

  const load = useCallback(async (cursor?: string) => {
    if (!persisted) return
    activeRequest.current?.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    setLoading(true)
    setFailure(null)
    if (!cursor) { setItems([]); setNextCursor(null) }
    try {
      const page = await client.fetchTicketActivity(ticketId, cursor, controller.signal)
      if (controller.signal.aborted) return
      setItems((current) => {
        if (!cursor) return page.items
        const seen = new Set(current.map((item) => item.id))
        return [...current, ...page.items.filter((item) => !seen.has(item.id))]
      })
      setNextCursor(page.nextCursor)
    } catch (error: unknown) {
      if (controller.signal.aborted || (error instanceof ApiRequestError && error.kind === 'cancelled')) return
      if (error instanceof ApiError || error instanceof ApiRequestError) {
        setFailure({ message: error.message, cursor })
      } else if (error instanceof ApiContractError) {
        setFailure({ message: '处理记录响应不符合契约，请重试或联系管理员。', cursor })
      } else {
        setUnexpectedFailure(error instanceof Error ? error : new Error('Unexpected activity request failure', { cause: error }))
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [client, persisted, ticketId])

  useEffect(() => {
    void load()
    return () => activeRequest.current?.abort()
  }, [load])

  if (unexpectedFailure) throw unexpectedFailure
  return <section className="section-block activity-section" aria-label="处理记录" aria-busy={loading}>
    <h3 className="section-label"><History size={14} /> 处理记录 <span className="panel-meta">最新在前</span></h3>
    {!persisted && <p className="field-hint">连接业务服务后查看已保存的处理记录。</p>}
    {persisted && !loading && !failure && items.length === 0 && <p className="field-hint">暂无已保存的处理记录。历史演示数据不补造操作记录。</p>}
    <div className="timeline activity-timeline" role="list">
      {items.map((item) => <div className="timeline-item" role="listitem" key={item.id}>
        <span className="timeline-dot" aria-hidden="true" />
        <div className="activity-content">
          <div className="timeline-label">{item.detail}</div>
          <div className="timeline-detail">{item.actorLabel} · <time dateTime={item.createdAt} title={item.createdAt}>{activityDate.format(new Date(item.createdAt))}</time></div>
          <div className="activity-meta">{item.ticketVersion !== null && <span>关联版本 {item.ticketVersion}</span>}<span>Trace <code>{item.traceId}</code></span></div>
        </div>
      </div>)}
    </div>
    {failure && <div className="inline-error" role="alert">{failure.message}<button type="button" onClick={() => { void load(failure.cursor) }}>重新加载处理记录</button></div>}
    <div className="activity-footer">
      {loading && <p className="field-hint" role="status">正在加载处理记录…</p>}
      {!failure && nextCursor && <Button size="small" loading={loading} onClick={() => { void load(nextCursor) }}>加载更早记录</Button>}
      {!loading && !failure && items.length > 0 && <span className="field-hint">已显示 {items.length} 条{nextCursor ? '' : ' · 已到最早记录'}</span>}
      {persisted && !loading && !failure && <Button type="text" size="small" icon={<RefreshCw size={12} />} onClick={() => { void load() }}>刷新记录</Button>}
    </div>
  </section>
}
