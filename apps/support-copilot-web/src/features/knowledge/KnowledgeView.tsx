import { useEffect, useState } from 'react'
import { Button, Empty, Input, Select, Spin, Tag } from 'antd'
import { Search } from 'lucide-react'
import type { ApiClient, ReleaseAction } from '../../services/api'
import { ApiError, ApiRequestError } from '../../services/api'
import type { KnowledgeHit, KnowledgeRelease } from '../../services/resourceSchemas'
import type { KnowledgeArticle } from '../../types'
import { UnavailablePanel } from '../shared/presentation'

type KnowledgeState =
  | { readonly kind: 'loading' }
  | { readonly kind: 'ready'; readonly hits: readonly KnowledgeHit[]; readonly releases: readonly KnowledgeRelease[]; readonly readOnly: boolean }
  | { readonly kind: 'unauthenticated' }
  | { readonly kind: 'error'; readonly message: string }

type KnowledgeViewProps = {
  readonly client: ApiClient
  readonly demoArticles: readonly KnowledgeArticle[] | null
}

export function KnowledgeView({ client, demoArticles }: KnowledgeViewProps) {
  if (demoArticles !== null) return <DemoKnowledgeView articles={demoArticles} />
  return <SecuredKnowledgeView client={client} />
}

function SecuredKnowledgeView({ client }: { readonly client: ApiClient }) {
  const [query, setQuery] = useState('')
  const [state, setState] = useState<KnowledgeState>({ kind: 'loading' })
  useEffect(() => {
    let active = true
    Promise.all([client.searchKnowledge('', 10), client.fetchKnowledgeReleases()])
      .then(([hits, releases]) => { if (active) setState({ kind: 'ready', hits, releases, readOnly: false }) })
      .catch((error: unknown) => {
        if (!active || (error instanceof ApiRequestError && error.kind === 'cancelled')) return
        if (error instanceof ApiError && error.status === 401) setState({ kind: 'unauthenticated' })
        else setState({ kind: 'error', message: error instanceof ApiError ? error.message : '知识服务暂不可用' })
      })
    return () => { active = false }
  }, [client])

  const search = async () => {
    if (state.kind !== 'ready') return
    setState({ kind: 'loading' })
    try {
      const [hits, releases] = await Promise.all([client.searchKnowledge(query, 10), client.fetchKnowledgeReleases()])
      setState({ kind: 'ready', hits, releases, readOnly: state.readOnly })
    } catch (error: unknown) {
      setState({ kind: 'error', message: error instanceof ApiError ? error.message : '知识检索失败' })
    }
  }

  const transition = async (release: KnowledgeRelease, action: ReleaseAction) => {
    if (state.kind !== 'ready') return
    try {
      const updated = await client.transitionKnowledgeRelease(release.releaseId, action, release.version)
      setState({ ...state, releases: state.releases.map((item) => item.releaseId === updated.releaseId ? updated : item) })
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 403) {
        setState({ ...state, readOnly: true })
        return
      }
      setState({ kind: 'error', message: error instanceof ApiError ? error.message : '知识发布操作失败' })
    }
  }

  switch (state.kind) {
    case 'loading': return <div className="view-enter"><section className="knowledge-panel data-loading" role="status"><Spin /><span>正在加载知识目录</span></section></div>
    case 'unauthenticated': return <div className="view-enter"><UnavailablePanel title="需要登录" description="安全模式未提供访问令牌，知识请求已由后端拒绝。" /></div>
    case 'error': return <div className="view-enter"><UnavailablePanel title="知识服务暂不可用" description={state.message} /></div>
    case 'ready': return <div className="view-enter"><section className="knowledge-panel">
      <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">知识检索与发布</h2><div className="panel-meta">{state.hits.length} 条命中 · {state.releases.length} 个发布版本</div></div></div>
      {state.readOnly && <div className="inline-role-state" role="status">当前身份仅可查看知识发布</div>}
      <div className="knowledge-toolbar"><Input prefix={<Search size={14} />} allowClear value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索已授权知识" onPressEnter={search} /><Button onClick={search}>搜索</Button></div>
      <div className="knowledge-list">{state.hits.length === 0 ? <div className="empty-queue"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的知识证据" /></div> : state.hits.map((hit) => <div className="knowledge-row" key={hit.chunkId}><div className="knowledge-main-cell"><div className="knowledge-title">{hit.documentTitle}</div><div className="knowledge-coverage"><span className="coverage-tag">{hit.section}</span></div><div className="knowledge-hit-copy">{hit.content}</div></div><div><span className="knowledge-cell-label">类型</span><span className="knowledge-cell-value">{hit.documentType}</span></div><div><span className="knowledge-cell-label">相关度</span><span className="knowledge-cell-value">{(hit.score * 100).toFixed(1)}</span></div></div>)}</div>
      <div className="panel-header"><div className="panel-heading"><h2 className="panel-title">发布版本</h2><div className="panel-meta">版本变更由后端审计</div></div></div>
      <div className="knowledge-list">{state.releases.map((release) => <ReleaseRow key={release.releaseId} release={release} readOnly={state.readOnly} onTransition={transition} />)}</div>
    </section></div>
    default: return state
  }
}

function ReleaseRow({ release, readOnly, onTransition }: { readonly release: KnowledgeRelease; readonly readOnly: boolean; readonly onTransition: (release: KnowledgeRelease, action: ReleaseAction) => void }) {
  const action = release.status === 'DRAFT' ? 'approve' : release.status === 'APPROVED' ? 'publish' : 'rollback'
  const label = action === 'approve' ? '批准' : action === 'publish' ? '发布' : '回滚'
  return <div className="knowledge-row"><div className="knowledge-main-cell"><div className="knowledge-title">{release.releaseId}</div><div className="knowledge-coverage">{release.allowedScopes.map((scope) => <span className="coverage-tag" key={scope}>{scope}</span>)}</div></div><div><span className="knowledge-cell-label">版本</span><span className="knowledge-cell-value">{release.releaseVersion}</span></div><div><span className="knowledge-cell-label">状态</span><Tag>{release.status}</Tag></div><Button size="small" disabled={readOnly} onClick={() => onTransition(release, action)}>{label}</Button></div>
}

function DemoKnowledgeView({ articles }: { readonly articles: readonly KnowledgeArticle[] }) {
  const [query, setQuery] = useState('')
  const [documentType, setDocumentType] = useState('ALL')
  const filtered = articles.filter((article) => [article.title, article.owner, ...article.coverage].join(' ').toLowerCase().includes(query.trim().toLowerCase()) && (documentType === 'ALL' || article.documentType === documentType))
  const chunkCount = filtered.reduce((total, article) => total + article.chunkCount, 0)
  return <div className="view-enter"><section className="knowledge-panel"><div className="panel-header"><div className="panel-heading"><h2 className="panel-title">知识文档</h2><div className="panel-meta">{filtered.length} 份文档 · {chunkCount} 个片段 · 演示数据</div></div></div>
    <div className="knowledge-toolbar"><Input prefix={<Search size={14} />} allowClear value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索文档、负责人或覆盖主题" /><Select value={documentType} onChange={setDocumentType} options={[{ value: 'ALL', label: '全部类型' }, { value: 'POLICY', label: '政策' }, { value: 'RUNBOOK', label: '处理手册' }, { value: 'FAQ', label: 'FAQ' }]} /></div>
    <div className="knowledge-list">{filtered.map((article) => <div className="knowledge-row" key={article.id}><div className="knowledge-main-cell"><div className="knowledge-title">{article.title}</div><div className="knowledge-coverage">{article.coverage.map((item) => <span className="coverage-tag" key={item}>{item}</span>)}</div></div><div><span className="knowledge-cell-label">负责人</span><span className="knowledge-cell-value">{article.owner}</span></div><div><span className="knowledge-cell-label">版本</span><span className="knowledge-cell-value">{article.version}</span></div><div><span className="knowledge-cell-label">片段</span><span className="knowledge-cell-value">{article.chunkCount} chunks</span></div><Tag color={article.status === 'ACTIVE' ? 'green' : 'gold'}>{article.status === 'ACTIVE' ? '已生效' : '索引中'}</Tag></div>)}</div>
  </section></div>
}
