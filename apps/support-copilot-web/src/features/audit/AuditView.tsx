import { useEffect, useState } from 'react'
import { Button, Empty, Spin, Tag } from 'antd'
import type { ApiClient } from '../../services/api'
import { ApiError, ApiRequestError } from '../../services/api'
import type { AuditEvent } from '../../services/resourceSchemas'
import { UnavailablePanel } from '../shared/presentation'
import { formatDate } from '../shared/presentationData'

type AuditState =
  | { readonly kind: 'loading' }
  | { readonly kind: 'ready'; readonly items: readonly AuditEvent[]; readonly nextCursor: string | null; readonly loadingMore: boolean }
  | { readonly kind: 'unauthenticated' | 'forbidden' }
  | { readonly kind: 'error'; readonly message: string }

const actionLabels: Readonly<Record<AuditEvent['action'], string>> = {
  TICKET_CREATED: '创建工单', TICKET_UPDATED: '更新工单', TICKET_UNASSIGNED: '取消负责人',
  ANALYSIS_PERSISTED: '保存分析', ANALYSIS_REVIEW_APPROVED: '采纳回复',
  ANALYSIS_REVIEW_EDITED: '编辑后采纳', ANALYSIS_REVIEW_REJECTED: '拒绝回复',
  KNOWLEDGE_RELEASE_DRAFT_CREATED: '创建知识草稿', KNOWLEDGE_RELEASE_APPROVED: '批准知识版本',
  KNOWLEDGE_RELEASE_PUBLISHED: '发布知识版本', KNOWLEDGE_RELEASE_ROLLED_BACK: '回滚知识版本',
}

export function AuditView({ client }: { readonly client: ApiClient }) {
  const [state, setState] = useState<AuditState>({ kind: 'loading' })
  useEffect(() => {
    let active = true
    client.fetchAuditEvents().then((page) => {
      if (active) setState({ kind: 'ready', items: page.items, nextCursor: page.nextCursor, loadingMore: false })
    }).catch((error: unknown) => {
      if (!active || (error instanceof ApiRequestError && error.kind === 'cancelled')) return
      if (error instanceof ApiError && error.status === 401) setState({ kind: 'unauthenticated' })
      else if (error instanceof ApiError && error.status === 403) setState({ kind: 'forbidden' })
      else setState({ kind: 'error', message: error instanceof ApiError ? error.message : '审计服务暂不可用' })
    })
    return () => { active = false }
  }, [client])

  const loadMore = async () => {
    if (state.kind !== 'ready' || state.nextCursor === null || state.loadingMore) return
    setState({ ...state, loadingMore: true })
    try {
      const page = await client.fetchAuditEvents(state.nextCursor)
      setState({ kind: 'ready', items: [...state.items, ...page.items], nextCursor: page.nextCursor, loadingMore: false })
    } catch (error: unknown) {
      setState({ kind: 'error', message: error instanceof ApiError ? error.message : '审计分页加载失败' })
    }
  }

  switch (state.kind) {
    case 'loading': return <div className="view-enter"><section className="knowledge-panel data-loading" role="status"><Spin /><span>正在加载审计记录</span></section></div>
    case 'unauthenticated': return <div className="view-enter"><UnavailablePanel title="需要登录" description="安全模式未提供访问令牌，审计请求已由后端拒绝。" /></div>
    case 'forbidden': return <div className="view-enter"><UnavailablePanel title="需要审核员或管理员权限" description="当前身份无权查看审计记录，后端已返回 403。" /></div>
    case 'error': return <div className="view-enter"><UnavailablePanel title="审计记录暂不可用" description={state.message} /></div>
    case 'ready': return <div className="view-enter"><section className="knowledge-panel"><div className="panel-header"><div className="panel-heading"><h2 className="panel-title">审计记录</h2><div className="panel-meta">按创建时间与事件编号进行游标分页</div></div></div>
      <div className="evaluation-table-wrap">{state.items.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无审计记录" /> : <table className="evaluation-table"><thead><tr><th>时间</th><th>动作</th><th>目标</th><th>执行身份</th><th>Trace ID</th></tr></thead><tbody>{state.items.map((event) => <tr key={event.id}><td>{formatDate(event.createdAt)}</td><td><Tag>{actionLabels[event.action]}</Tag></td><td>{event.targetType} · {event.targetId}</td><td>{event.actorSubject}</td><td>{event.traceId}</td></tr>)}</tbody></table>}</div>
      {state.nextCursor !== null && <div className="pagination-actions"><Button loading={state.loadingMore} onClick={loadMore}>加载更多</Button></div>}
    </section></div>
    default: return state
  }
}
