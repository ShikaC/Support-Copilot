import { lazy, Suspense, useMemo, useState } from 'react'
import { AlertTriangle, BarChart3, BookOpen, CheckCircle2, ChevronDown, ClipboardList, Inbox, LayoutDashboard } from 'lucide-react'
import { ConfigProvider } from 'antd'
import { configuredAuthMode, createAuthSession, type AuthMode } from './auth/authSession'
import { RetryableLazyViewBoundary } from './components/RetryableLazyViewBoundary'
import { demoKnowledgeArticles } from './data/demoData'
import { WorkbenchView } from './features/workbench/WorkbenchView'
import { useTicketWorkflow } from './features/workbench/useTicketWorkflow'
import { createApiClient } from './services/api'
import './App.css'

type ViewKey = 'workbench' | 'overview' | 'knowledge' | 'audit' | 'quality'
type OverviewModule = typeof import('./features/overview/OverviewView')
type OverviewLoader = () => Promise<OverviewModule>
type AppProps = {
  readonly authMode?: AuthMode
  readonly overviewLoader?: OverviewLoader
}

const loadOverview = () => import('./features/overview/OverviewView')
const createLazyViews = (overviewLoader: OverviewLoader) => ({
  OverviewView: lazy(() => overviewLoader().then((module) => ({ default: module.OverviewView }))),
  KnowledgeView: lazy(() => import('./features/knowledge/KnowledgeView').then((module) => ({ default: module.KnowledgeView }))),
  AuditView: lazy(() => import('./features/audit/AuditView').then((module) => ({ default: module.AuditView }))),
  QualityView: lazy(() => import('./features/quality/QualityView').then((module) => ({ default: module.QualityView }))),
})

const navigation: ReadonlyArray<{ readonly key: ViewKey; readonly label: string; readonly icon: typeof Inbox }> = [
  { key: 'workbench', label: '工单工作台', icon: Inbox },
  { key: 'overview', label: '运营概览', icon: LayoutDashboard },
  { key: 'knowledge', label: '知识库', icon: BookOpen },
  { key: 'audit', label: '审计记录', icon: ClipboardList },
  { key: 'quality', label: '质量评估', icon: BarChart3 },
]
const viewCopy: Readonly<Record<ViewKey, { readonly title: string; readonly subtitle: string }>> = {
  workbench: { title: '工单工作台', subtitle: '审核分类、知识证据与回复建议' },
  overview: { title: '运营概览', subtitle: '队列状态、处理效率与服务质量' },
  knowledge: { title: '知识库', subtitle: '文档版本、索引状态与覆盖范围' },
  audit: { title: '审计记录', subtitle: '可信业务变更与人工审核轨迹' },
  quality: { title: '质量评估', subtitle: '检索、生成与人工反馈基线' },
}

export function App({ authMode = configuredAuthMode(), overviewLoader = loadOverview }: AppProps) {
  const [view, setView] = useState<ViewKey>('workbench')
  const [lazyViews, setLazyViews] = useState(() => createLazyViews(overviewLoader))
  const auth = useMemo(() => createAuthSession({ mode: authMode }), [authMode])
  const client = useMemo(() => createApiClient({
    auth, baseUrl: import.meta.env.VITE_API_BASE_URL ?? '', timeoutMs: 8000,
  }), [auth])
  const workflow = useTicketWorkflow({ auth, client })
  const authState = auth.state()
  const currentCopy = viewCopy[view]
  const { OverviewView, KnowledgeView, AuditView, QualityView } = lazyViews
  const userLabel = authState.mode === 'demo' ? '演示管理员' : authState.status === 'authenticated' ? '已认证用户' : '未登录'
  const avatar = authState.mode === 'demo' ? 'CY' : authState.status === 'authenticated' ? 'ID' : '--'

  return <ConfigProvider theme={{ token: {
    colorPrimary: '#16775f', colorText: '#344039', colorTextSecondary: '#68736d',
    colorBorder: '#d9ded9', colorBgContainer: '#fffefa', borderRadius: 6,
    fontFamily: "Aptos, 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif", controlHeight: 34,
  } }}>
    <a className="skip-link" href="#main-content">跳到主要内容</a>
    <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">SC</span><span><span className="brand-name">Support Copilot</span><span className="brand-context">服务运营控制台</span></span></div><div className="nav-section-label">工作区</div>
      <Navigation className="nav-list" label="主导航" view={view} onChange={setView} />
      <div className="sidebar-footer"><ServiceState state={workflow.apiState} authMode={auth.mode} /></div>
    </aside>
    <div className="app-body"><header className={`topbar ${workflow.toast ? 'has-toast' : ''}`}><div><h1 className="page-title">{currentCopy.title}</h1><p className="page-subtitle">{currentCopy.subtitle}</p></div><div className="topbar-actions"><button className="user-menu" type="button" onClick={() => workflow.showToast(authState.mode === 'demo' ? '当前为面试演示账号' : authState.status === 'authenticated' ? '当前使用会话访问令牌' : '当前安全模式尚未登录')}><span className="user-avatar">{avatar}</span><span className="user-name">{userLabel}</span><ChevronDown size={13} /></button>{workflow.toast && <div className="topbar-toast" aria-label="操作反馈"><div className={`toast ${workflow.toast.kind}`} role={workflow.toast.kind === 'error' ? 'alert' : 'status'}>{workflow.toast.kind === 'error' ? <AlertTriangle /> : <CheckCircle2 />}<span>{workflow.toast.message}</span></div></div>}</div></header>
      <Navigation className="mobile-nav" label="移动端导航" view={view} onChange={setView} />
      <main className="page-content" id="main-content"><RetryableLazyViewBoundary onRetry={() => setLazyViews(createLazyViews(overviewLoader))}><Suspense fallback={<div className="view-enter"><section className="knowledge-panel data-loading" role="status">正在加载页面</section></div>}>
        {view === 'workbench' && <WorkbenchView tickets={workflow.tickets} selectedTicket={workflow.selectedTicket} client={client} metrics={workflow.metrics} analyzing={workflow.selectedTicket !== null && workflow.analyzingTicketIds.includes(workflow.selectedTicket.id)} onSelect={workflow.setSelectedTicketId} onAnalyze={workflow.runAnalysis} onReviewSaved={workflow.recordReview} onRefreshTicket={workflow.reconcileTicket} onAssign={workflow.assignSelectedTicket} onUnassign={workflow.unassignSelectedTicket} assigneeUpdating={workflow.selectedTicket !== null && workflow.assigneeTicketIds.includes(workflow.selectedTicket.id)} onToast={workflow.showToast} />}
        {view === 'overview' && <OverviewView metrics={workflow.metrics} tickets={workflow.tickets} />}
        {view === 'knowledge' && <KnowledgeView client={client} demoArticles={workflow.apiState === 'demo' ? demoKnowledgeArticles : null} />}
        {view === 'audit' && <AuditView client={client} />}
        {view === 'quality' && <QualityView metrics={workflow.metrics} metricsError={workflow.metricsError} />}
      </Suspense></RetryableLazyViewBoundary></main>
    </div></div>
  </ConfigProvider>
}

function Navigation({ className, label, view, onChange }: { readonly className: string; readonly label: string; readonly view: ViewKey; readonly onChange: (view: ViewKey) => void }) {
  return <nav className={className} aria-label={label}>{navigation.map((item) => {
    const Icon = item.icon
    return <button className={`nav-item ${view === item.key ? 'active' : ''}`} type="button" key={item.key} onClick={() => onChange(item.key)}><Icon /><span>{item.label}</span></button>
  })}</nav>
}

function ServiceState({ state, authMode }: { readonly state: ReturnType<typeof useTicketWorkflow>['apiState']; readonly authMode: AuthMode }) {
  const label = state === 'connected' ? '业务 API 已连接' : state === 'connecting' ? '正在检查服务' : state === 'partial' ? '部分服务可用' : state === 'unauthenticated' ? '需要登录' : state === 'unavailable' ? '安全服务不可用' : '演示数据模式'
  const detail = state === 'connected' ? '工单与指标来自本地服务' : state === 'partial' ? '部分数据暂不可用，页面未伪造缺失指标' : state === 'connecting' ? '正在读取业务服务' : state === 'unauthenticated' ? '安全请求未使用演示身份' : state === 'unavailable' ? '安全请求失败，未切换到演示身份' : authMode === 'demo' ? '无需 API Key 也可审查完整界面' : '安全服务当前不可用'
  return <div className="service-state"><div className="service-state-row"><span className={`service-state-dot ${state === 'connected' ? '' : 'demo'}`} /><span>{label}</span></div><small>{detail}</small></div>
}

export default App
