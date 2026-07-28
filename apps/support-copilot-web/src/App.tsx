import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleGauge,
  Clock3,
  FileSearch,
  Inbox,
  LayoutDashboard,
  Link2,
  Play,
  RefreshCw,
  Search,
  Send,
  UserRound,
} from 'lucide-react'
import {
  Button,
  ConfigProvider,
  Empty,
  Input,
  Progress,
  Segmented,
  Select,
  Spin,
  Tabs,
  Tag,
  Tooltip,
} from 'antd'
import ReactECharts from 'echarts-for-react'
import { analyzeTicket, fetchMetrics, fetchTickets, updateTicket } from './services/api'
import {
  createDemoAnalysis,
  demoKnowledgeArticles,
  demoMetrics,
  demoTickets,
} from './data/demoData'
import type {
  AnalysisResult,
  KnowledgeArticle,
  Metrics,
  Priority,
  Ticket,
  TicketStatus,
} from './types'
import './App.css'

type ViewKey = 'workbench' | 'overview' | 'knowledge' | 'quality'

const categoryLabels: Record<string, string> = {
  BILLING: '账单支付',
  ACCOUNT_ACCESS: '账号访问',
  INVOICE: '发票服务',
  DATA_EXPORT: '数据导出',
  SUBSCRIPTION: '订阅咨询',
  PRIVACY: '隐私合规',
  TECHNICAL: '技术问题',
  DATA_RECOVERY: '数据恢复',
}

const priorityLabels: Record<Priority, string> = {
  URGENT: '紧急',
  HIGH: '高',
  MEDIUM: '中',
  LOW: '低',
}

const statusLabels: Record<TicketStatus, string> = {
  NEW: '新工单',
  ANALYZING: '分析中',
  READY_FOR_REVIEW: '待审核',
  IN_PROGRESS: '处理中',
  NEEDS_ESCALATION: '需升级',
  WAITING_CUSTOMER: '等待客户',
  RESOLVED: '已解决',
  CLOSED: '已关闭',
  READY_FOR_MANUAL_REVIEW: '人工复核',
}

const statusColors: Record<TicketStatus, string> = {
  NEW: 'blue',
  ANALYZING: 'gold',
  READY_FOR_REVIEW: 'cyan',
  IN_PROGRESS: 'processing',
  NEEDS_ESCALATION: 'red',
  WAITING_CUSTOMER: 'orange',
  RESOLVED: 'green',
  CLOSED: 'default',
  READY_FOR_MANUAL_REVIEW: 'volcano',
}

const navigation: Array<{ key: ViewKey; label: string; icon: typeof Inbox }> = [
  { key: 'workbench', label: '工单工作台', icon: Inbox },
  { key: 'overview', label: '运营概览', icon: LayoutDashboard },
  { key: 'knowledge', label: '知识库', icon: BookOpen },
  { key: 'quality', label: '质量评估', icon: BarChart3 },
]

const viewCopy: Record<ViewKey, { title: string; subtitle: string }> = {
  workbench: { title: '工单工作台', subtitle: '审核分类、知识证据与回复建议' },
  overview: { title: '运营概览', subtitle: '队列状态、处理效率与服务质量' },
  knowledge: { title: '知识库', subtitle: '文档版本、索引状态与覆盖范围' },
  quality: { title: '质量评估', subtitle: '检索、生成与人工反馈基线' },
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function secondsUntil(value: string) {
  return Math.floor((new Date(value).getTime() - Date.now()) / 1000)
}

function slaLabel(value: string) {
  const seconds = secondsUntil(value)
  if (seconds <= 0) return 'SLA 已超时'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.max(0, Math.floor((seconds % 3600) / 60))
  return hours > 0 ? `${hours}小时${minutes}分` : `${minutes}分钟`
}

function isAbortError(error: unknown) {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    error.name === 'AbortError'
  )
}

function StatusStrip({ metrics }: { metrics: Metrics }) {
  const items = [
    {
      label: '待处理工单',
      value: metrics.summary.openTickets,
      delta: '+6 今日',
      icon: Inbox,
      tone: '',
    },
    {
      label: '紧急优先级',
      value: metrics.summary.urgentTickets,
      delta: '2 条临近 SLA',
      icon: AlertTriangle,
      tone: 'danger',
    },
    {
      label: 'SLA 风险',
      value: metrics.summary.slaRiskTickets,
      delta: '较昨日 -2',
      icon: Clock3,
      tone: 'warning',
    },
    {
      label: '分析成功率',
      value: `${(metrics.summary.analysisSuccessRate * 100).toFixed(1)}%`,
      delta: '+1.8%',
      icon: CircleGauge,
      tone: 'neutral',
    },
  ]

  return (
    <section className="status-strip" aria-label="队列状态">
      {items.map((item) => {
        const Icon = item.icon
        return (
          <div className="status-metric" key={item.label}>
            <span className={`metric-icon ${item.tone}`}>
              <Icon aria-hidden="true" />
            </span>
            <span>
              <span className="metric-label">{item.label}</span>
              <span className="metric-value">
                {item.value}
                <span className="metric-delta">{item.delta}</span>
              </span>
            </span>
          </div>
        )
      })}
    </section>
  )
}

function TicketQueue({
  tickets,
  selectedTicketId,
  onSelect,
}: {
  tickets: Ticket[]
  selectedTicketId: string
  onSelect: (ticketId: string) => void
}) {
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<string | number>('待处理')
  const [priority, setPriority] = useState<string>('ALL')

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return tickets.filter((ticket) => {
      const scopeMatches =
        scope === '全部' ||
        (scope === '待处理' && !['RESOLVED', 'CLOSED'].includes(ticket.status)) ||
        (scope === '需升级' && ticket.status === 'NEEDS_ESCALATION')
      const priorityMatches = priority === 'ALL' || ticket.priority === priority
      const queryMatches =
        !normalized ||
        [ticket.ticketNo, ticket.subject, ticket.customerName, ticket.customerCompany]
          .join(' ')
          .toLowerCase()
          .includes(normalized)
      return scopeMatches && priorityMatches && queryMatches
    })
  }, [priority, query, scope, tickets])

  return (
    <section className="workspace-column queue-column" aria-label="工单队列">
      <div className="panel-header">
        <div className="panel-heading">
          <h2 className="panel-title">工单队列</h2>
          <div className="panel-meta">{filtered.length} 条匹配结果</div>
        </div>
      </div>
      <div className="queue-controls">
        <Input
          allowClear
          prefix={<Search size={14} />}
          placeholder="搜索编号、客户或标题"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="queue-filter-row">
          <Segmented
            block
            options={['待处理', '需升级', '全部']}
            size="small"
            value={scope}
            onChange={setScope}
          />
          <Select
            aria-label="按优先级筛选"
            value={priority}
            onChange={setPriority}
            options={[
              { value: 'ALL', label: '全部优先级' },
              { value: 'URGENT', label: '紧急' },
              { value: 'HIGH', label: '高' },
              { value: 'MEDIUM', label: '中' },
              { value: 'LOW', label: '低' },
            ]}
            size="small"
          />
        </div>
      </div>
      <div className="ticket-list">
        {filtered.length === 0 ? (
          <div className="empty-queue">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的工单" />
          </div>
        ) : (
          filtered.map((ticket) => {
            const slaRisk = secondsUntil(ticket.slaDeadline) < 2 * 3600
            return (
              <button
                className={`ticket-row ${ticket.id === selectedTicketId ? 'selected' : ''}`}
                type="button"
                key={ticket.id}
                onClick={() => onSelect(ticket.id)}
              >
                <span className="ticket-row-top">
                  <span className="ticket-no">{ticket.ticketNo}</span>
                  <span className="priority-label">
                    <span className={`priority-dot ${ticket.priority}`} />
                    {priorityLabels[ticket.priority]}
                  </span>
                </span>
                <span className="ticket-subject">{ticket.subject}</span>
                <span className="ticket-row-bottom">
                  <span className="ticket-company">{ticket.customerCompany}</span>
                  <span className={`sla-time ${slaRisk ? 'risk' : ''}`}>
                    {slaLabel(ticket.slaDeadline)}
                  </span>
                </span>
              </button>
            )
          })
        )}
      </div>
    </section>
  )
}

function TicketDetail({
  ticket,
  analyzing,
  onAnalyze,
  onAssign,
}: {
  ticket: Ticket
  analyzing: boolean
  onAnalyze: () => void
  onAssign: () => void
}) {
  return (
    <section className="workspace-column detail-column" aria-label="工单详情">
      <div className="panel-header">
        <div className="panel-heading">
          <h2 className="panel-title">工单详情</h2>
          <div className="panel-meta">更新于 {formatDate(ticket.updatedAt)}</div>
        </div>
      </div>
      <div className="detail-scroll">
        <div className="detail-meta-row">
          <Tag color={statusColors[ticket.status]}>{statusLabels[ticket.status]}</Tag>
          <span className="ticket-no">{ticket.ticketNo}</span>
        </div>
        <h2 className="ticket-detail-title">{ticket.subject}</h2>
        <div className="ticket-detail-company">
          {ticket.customerName} · {ticket.customerCompany}
          <span className="customer-tier">{ticket.customerTier}</span>
        </div>

        <div className="detail-actions">
          <Button
            type="primary"
            icon={analyzing ? <Spin size="small" /> : <Play size={14} />}
            loading={analyzing}
            onClick={onAnalyze}
          >
            {ticket.latestAnalysis ? '重新分析' : '开始分析'}
          </Button>
          <Button icon={<UserRound size={14} />} onClick={onAssign}>
            {ticket.assigneeName ? '重新分配' : '领取工单'}
          </Button>
        </div>

        <div className="detail-grid">
          <div>
            <span className="detail-label">当前分类</span>
            <span className="detail-value">{categoryLabels[ticket.category] ?? ticket.category}</span>
          </div>
          <div>
            <span className="detail-label">负责人</span>
            <span className="detail-value">{ticket.assigneeName ?? '未分配'}</span>
          </div>
          <div>
            <span className="detail-label">来源渠道</span>
            <span className="detail-value">{ticket.channel.replace('_', ' ')}</span>
          </div>
          <div>
            <span className="detail-label">SLA 剩余</span>
            <span className="detail-value">{slaLabel(ticket.slaDeadline)}</span>
          </div>
        </div>

        <div className="section-block">
          <h3 className="section-label">客户问题</h3>
          <div className="message-body">{ticket.description}</div>
        </div>

        <div className="section-block">
          <h3 className="section-label">处理记录</h3>
          {ticket.events.length === 0 ? (
            <div className="timeline-item">
              <span className="timeline-dot" />
              <div>
                <div className="timeline-label">工单已进入队列</div>
                <div className="timeline-detail">等待客服处理</div>
              </div>
              <span className="timeline-time">{formatTime(ticket.createdAt)}</span>
            </div>
          ) : (
            <div className="timeline">
              {ticket.events.map((event) => (
                <div className="timeline-item" key={event.id}>
                  <span className="timeline-dot" />
                  <div>
                    <div className="timeline-label">{event.label}</div>
                    <div className="timeline-detail">{event.detail}</div>
                  </div>
                  <span className="timeline-time">{formatTime(event.createdAt)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function WorkflowPanel({ analysis }: { analysis: AnalysisResult }) {
  return (
    <div className="analysis-content">
      <div className="analysis-summary">
        <div className="analysis-fact">
          <span className="analysis-fact-label">建议分类</span>
          <span className="analysis-fact-value">
            {categoryLabels[analysis.classification.category] ?? analysis.classification.category}
          </span>
        </div>
        <div className="analysis-fact">
          <span className="analysis-fact-label">建议优先级</span>
          <span className="analysis-fact-value">
            {priorityLabels[analysis.classification.priority]}
          </span>
        </div>
        <div className="analysis-fact">
          <span className="analysis-fact-label">客户情绪</span>
          <span className="analysis-fact-value">
            {analysis.classification.sentiment === 'NEGATIVE' ? '负向' : '中性'}
          </span>
        </div>
        <div className="analysis-fact">
          <span className="analysis-fact-label">处理建议</span>
          <span className="analysis-fact-value">
            {analysis.decision.escalationRequired ? '升级人工' : '一线审核'}
          </span>
        </div>
      </div>

      <div className="confidence-row">
        <div className="confidence-copy">
          <span>分类置信度</span>
          <strong>{(analysis.classification.confidence * 100).toFixed(0)}%</strong>
        </div>
        <Progress
          percent={analysis.classification.confidence * 100}
          showInfo={false}
          strokeColor="oklch(0.48 0.11 162)"
          railColor="oklch(0.92 0.008 100)"
          size="small"
        />
      </div>

      <div className="analysis-reason">{analysis.classification.reasonSummary}</div>

      <div className="section-heading-row">
        <h3 className="section-label">处理轨迹</h3>
        <span className={`mode-badge ${analysis.mode}`}>
          {analysis.mode === 'live' ? 'LIVE' : analysis.mode === 'mock' ? 'DEMO' : 'FALLBACK'}
        </span>
      </div>
      <div className="workflow-list">
        {analysis.workflowSteps.map((step) => (
          <div className="workflow-step" key={step.id}>
            <span className={`step-icon ${step.status}`}>
              {step.status === 'complete' ? (
                <Check size={13} />
              ) : step.status === 'running' ? (
                <RefreshCw size={13} />
              ) : step.status === 'failed' ? (
                <AlertTriangle size={13} />
              ) : (
                <Clock3 size={13} />
              )}
            </span>
            <div>
              <div className="step-name">{step.name}</div>
              <div className="step-description">{step.description}</div>
            </div>
            <span className="step-duration">
              {step.durationMs == null ? '等待' : `${step.durationMs} ms`}
            </span>
          </div>
        ))}
      </div>
      <div className="trace-meta">
        <span>{analysis.traceId}</span>
        <span>{analysis.promptVersion}</span>
      </div>
    </div>
  )
}

function EvidencePanel({ analysis }: { analysis: AnalysisResult }) {
  const [expandedId, setExpandedId] = useState<string | null>(
    analysis.retrieval.hits[0]?.chunkId ?? null,
  )

  useEffect(() => {
    setExpandedId(analysis.retrieval.hits[0]?.chunkId ?? null)
  }, [analysis.id, analysis.retrieval.hits])

  return (
    <div className="analysis-content">
      <div className="retrieval-query">
        <span className="retrieval-query-label">检索查询</span>
        <span className="retrieval-query-value">{analysis.retrieval.query}</span>
      </div>

      {analysis.retrieval.hits.length === 0 ? (
        <div className="no-evidence">
          <FileSearch size={20} />
          <strong>没有找到充分证据</strong>
          <span>系统已停止自动下结论，并转入人工复核。</span>
        </div>
      ) : (
        <div className="evidence-list">
          {analysis.retrieval.hits.map((hit) => {
            const expanded = hit.chunkId === expandedId
            return (
              <article className="evidence-item" key={hit.chunkId}>
                <button
                  className="evidence-button"
                  type="button"
                  aria-expanded={expanded}
                  onClick={() => setExpandedId(expanded ? null : hit.chunkId)}
                >
                  <span className="evidence-rank">{hit.rerankPosition}</span>
                  <span>
                    <span className="evidence-title">{hit.documentTitle}</span>
                    <span className="evidence-section">{hit.section}</span>
                  </span>
                  <span className="evidence-score">{(hit.rerankScore * 100).toFixed(1)}</span>
                  {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                </button>
                <div className={`evidence-expanded ${expanded ? 'open' : ''}`}>
                  <div className="evidence-expanded-inner">
                    <p className="evidence-copy">{hit.content}</p>
                    <div className="evidence-meta">
                      <span>{hit.retrievalMethod}</span>
                      <span>{hit.usedAsEvidence ? '已作为证据' : '未进入上下文'}</span>
                    </div>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

function ReplyPanel({
  analysis,
  onToast,
}: {
  analysis: AnalysisResult
  onToast: (message: string) => void
}) {
  const [reply, setReply] = useState(analysis.suggestedReply.content)

  useEffect(() => {
    setReply(analysis.suggestedReply.content)
  }, [analysis.id, analysis.suggestedReply.content])

  return (
    <div className="analysis-content reply-editor">
      <Input.TextArea
        aria-label="建议回复"
        rows={10}
        value={reply}
        onChange={(event) => setReply(event.target.value)}
      />

      {analysis.suggestedReply.citations.length > 0 && (
        <div className="citation-list">
          {analysis.suggestedReply.citations.map((citation, index) => (
            <div className="citation-item" key={citation}>
              <Link2 />
              <span>
                [{index + 1}] {citation}
              </span>
            </div>
          ))}
        </div>
      )}

      {analysis.suggestedReply.warnings.length > 0 && (
        <div className="warning-list">
          {analysis.suggestedReply.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <AlertTriangle />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}

      <div className="reply-footer">
        <span className="reply-usage">
          {analysis.usage.inputTokens + analysis.usage.outputTokens} tokens ·{' '}
          {(analysis.usage.durationMs / 1000).toFixed(2)} s
        </span>
        <Button
          type="primary"
          icon={<Send size={13} />}
          disabled={!reply.trim()}
          onClick={() => onToast('回复建议已采纳，修改记录已写入审计日志')}
        >
          采纳回复
        </Button>
      </div>
    </div>
  )
}

function AnalysisColumn({
  ticket,
  analyzing,
  onAnalyze,
  onToast,
}: {
  ticket: Ticket
  analyzing: boolean
  onAnalyze: () => void
  onToast: (message: string) => void
}) {
  const analysis = ticket.latestAnalysis

  if (analyzing) {
    return (
      <section className="workspace-column analysis-column" aria-label="AI 分析">
        <div className="panel-header">
          <div className="panel-heading">
            <h2 className="panel-title">辅助分析</h2>
            <div className="panel-meta">正在执行知识检索与风险检查</div>
          </div>
        </div>
        <div className="analysis-content">
          <div className="workflow-list">
            {['内容预处理', '工单理解', '知识检索', '回复生成', '风险检查'].map(
              (name, index) => (
                <div className="workflow-step" key={name}>
                  <span className={`step-icon ${index === 0 ? 'running' : ''}`}>
                    {index === 0 ? <RefreshCw /> : <Clock3 />}
                  </span>
                  <div>
                    <div className="step-name">{name}</div>
                    <div className="step-description">
                      {index === 0 ? '正在处理当前工单内容' : '等待上一步完成'}
                    </div>
                  </div>
                  <span className="step-duration">{index === 0 ? '运行中' : '等待'}</span>
                </div>
              ),
            )}
          </div>
        </div>
      </section>
    )
  }

  if (!analysis) {
    return (
      <section className="workspace-column analysis-column" aria-label="AI 分析">
        <div className="panel-header">
          <div className="panel-heading">
            <h2 className="panel-title">辅助分析</h2>
            <div className="panel-meta">尚未运行</div>
          </div>
        </div>
        <div className="analysis-content">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="运行分析后将在这里显示处理轨迹与知识证据"
          />
        </div>
      </section>
    )
  }

  return (
    <section className="workspace-column analysis-column" aria-label="AI 分析">
      <div className="panel-header">
        <div className="panel-heading">
          <h2 className="panel-title">辅助分析</h2>
          <div className="panel-meta">
            {analysis.modelName} · {formatTime(analysis.createdAt)}
          </div>
        </div>
        <Tooltip title="刷新分析结果">
          <button className="icon-button" type="button" aria-label="刷新分析结果" onClick={onAnalyze}>
            <RefreshCw />
          </button>
        </Tooltip>
      </div>
      <div className="analysis-scroll">
        <Tabs
          className="analysis-tabs"
          defaultActiveKey="workflow"
          items={[
            {
              key: 'workflow',
              label: '处理轨迹',
              children: <WorkflowPanel analysis={analysis} />,
            },
            {
              key: 'evidence',
              label: `知识依据 ${analysis.retrieval.hits.length}`,
              children: <EvidencePanel analysis={analysis} />,
            },
            {
              key: 'reply',
              label: '回复建议',
              children: <ReplyPanel analysis={analysis} onToast={onToast} />,
            },
          ]}
        />
      </div>
    </section>
  )
}

function WorkbenchView({
  tickets,
  selectedTicket,
  metrics,
  analyzing,
  onSelect,
  onAnalyze,
  onAssign,
  onToast,
}: {
  tickets: Ticket[]
  selectedTicket: Ticket
  metrics: Metrics
  analyzing: boolean
  onSelect: (ticketId: string) => void
  onAnalyze: () => void
  onAssign: () => void
  onToast: (message: string) => void
}) {
  return (
    <div className="view-enter">
      <StatusStrip metrics={metrics} />
      <div className="workspace">
        <TicketQueue tickets={tickets} selectedTicketId={selectedTicket.id} onSelect={onSelect} />
        <TicketDetail
          ticket={selectedTicket}
          analyzing={analyzing}
          onAnalyze={onAnalyze}
          onAssign={onAssign}
        />
        <AnalysisColumn
          ticket={selectedTicket}
          analyzing={analyzing}
          onAnalyze={onAnalyze}
          onToast={onToast}
        />
      </div>
    </div>
  )
}

function OverviewView({ metrics, tickets }: { metrics: Metrics; tickets: Ticket[] }) {
  const trendOption = {
    animationDuration: 350,
    color: ['#1d8067', '#c4872c'],
    tooltip: { trigger: 'axis', borderWidth: 0, textStyle: { fontSize: 11 } },
    legend: {
      top: 8,
      right: 12,
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { color: '#66706a', fontSize: 10 },
    },
    grid: { top: 48, right: 22, bottom: 28, left: 38 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: metrics.ticketTrend.map((item) => item.date),
      axisLine: { lineStyle: { color: '#dde1dc' } },
      axisTick: { show: false },
      axisLabel: { color: '#7c847f', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#eceeea' } },
      axisLabel: { color: '#7c847f', fontSize: 10 },
    },
    series: [
      {
        name: '新建',
        type: 'line',
        smooth: 0.25,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2 },
        data: metrics.ticketTrend.map((item) => item.created),
      },
      {
        name: '解决',
        type: 'line',
        smooth: 0.25,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2 },
        data: metrics.ticketTrend.map((item) => item.resolved),
      },
    ],
  }

  const categoryOption = {
    animationDuration: 350,
    color: ['#397c68'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, borderWidth: 0 },
    grid: { top: 16, right: 30, bottom: 20, left: 78 },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#eceeea' } },
      axisLabel: { color: '#7c847f', fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: metrics.categoryDistribution.map((item) => item.category),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#59635d', fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        barWidth: 10,
        itemStyle: { borderRadius: 2 },
        data: metrics.categoryDistribution.map((item) => item.count),
      },
    ],
  }

  return (
    <div className="view-enter">
      <StatusStrip metrics={metrics} />
      <div className="dashboard-grid">
        <div>
          <section className="dashboard-panel">
            <div className="panel-header">
              <div className="panel-heading">
                <h2 className="panel-title">工单趋势</h2>
                <div className="panel-meta">最近 7 天新建与解决数量</div>
              </div>
              <Tag>最近 7 天</Tag>
            </div>
            <div className="chart-panel-body">
              <ReactECharts option={trendOption} style={{ height: '100%' }} />
            </div>
          </section>

          <section className="dashboard-panel">
            <div className="panel-header">
              <div className="panel-heading">
                <h2 className="panel-title">近期高风险工单</h2>
                <div className="panel-meta">按 SLA 截止时间排序</div>
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="recent-ticket-table">
                <thead>
                  <tr>
                    <th>工单</th>
                    <th>客户</th>
                    <th>状态</th>
                    <th className="numeric">SLA</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.slice(0, 5).map((ticket) => (
                    <tr key={ticket.id}>
                      <td>{ticket.subject}</td>
                      <td>{ticket.customerCompany}</td>
                      <td>{statusLabels[ticket.status]}</td>
                      <td className="numeric">{slaLabel(ticket.slaDeadline)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div>
          <section className="dashboard-panel">
            <div className="panel-header">
              <div className="panel-heading">
                <h2 className="panel-title">类别分布</h2>
                <div className="panel-meta">当前开放工单</div>
              </div>
            </div>
            <div className="chart-panel-body">
              <ReactECharts option={categoryOption} style={{ height: '100%' }} />
            </div>
          </section>

          <section className="dashboard-panel">
            <div className="panel-header">
              <div className="panel-heading">
                <h2 className="panel-title">辅助质量</h2>
                <div className="panel-meta">当前评估基线</div>
              </div>
            </div>
            <div className="quality-list">
              <div className="quality-row">
                <div>
                  <div className="quality-name">建议回复采纳率</div>
                  <div className="quality-context">编辑后采纳计入</div>
                </div>
                <span className="quality-value">
                  {(metrics.suggestionAcceptanceRate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="quality-row">
                <div>
                  <div className="quality-name">平均分析耗时</div>
                  <div className="quality-context">p95 {metrics.analysisLatency.p95Ms} ms</div>
                </div>
                <span className="quality-value">
                  {(metrics.analysisLatency.averageMs / 1000).toFixed(2)}s
                </span>
              </div>
              <div className="quality-row">
                <div>
                  <div className="quality-name">证据忠实度</div>
                  <div className="quality-context">离线评估集</div>
                </div>
                <span className="quality-value">
                  {(metrics.evaluation.groundedness * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function KnowledgeView({ articles }: { articles: KnowledgeArticle[] }) {
  const [query, setQuery] = useState('')
  const [documentType, setDocumentType] = useState('ALL')
  const filtered = articles.filter((article) => {
    const queryMatches = [article.title, article.owner, ...article.coverage]
      .join(' ')
      .toLowerCase()
      .includes(query.trim().toLowerCase())
    const typeMatches = documentType === 'ALL' || article.documentType === documentType
    return queryMatches && typeMatches
  })
  const visibleChunkCount = filtered.reduce((total, article) => total + article.chunkCount, 0)
  const indexingCount = filtered.filter((article) => article.status === 'INDEXING').length

  return (
    <div className="view-enter">
      <section className="knowledge-panel">
        <div className="panel-header">
          <div className="panel-heading">
            <h2 className="panel-title">知识文档</h2>
            <div className="panel-meta">
              {filtered.length} 份文档 · {visibleChunkCount} 个片段 · {indexingCount} 个索引任务运行中
            </div>
          </div>
        </div>
        <div className="knowledge-toolbar">
          <Input
            prefix={<Search size={14} />}
            allowClear
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索文档、负责人或覆盖主题"
          />
          <Select
            value={documentType}
            onChange={setDocumentType}
            options={[
              { value: 'ALL', label: '全部类型' },
              { value: 'POLICY', label: '政策' },
              { value: 'RUNBOOK', label: '处理手册' },
              { value: 'FAQ', label: 'FAQ' },
            ]}
          />
        </div>
        <div className="knowledge-list">
          {filtered.length === 0 ? (
            <div className="empty-queue">
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的知识文档" />
            </div>
          ) : (
            filtered.map((article) => (
              <div className="knowledge-row" key={article.id}>
                <div className="knowledge-main-cell">
                  <div className="knowledge-title">{article.title}</div>
                  <div className="knowledge-coverage">
                    {article.coverage.map((item) => (
                      <span className="coverage-tag" key={item}>{item}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="knowledge-cell-label">负责人</span>
                  <span className="knowledge-cell-value">{article.owner}</span>
                </div>
                <div>
                  <span className="knowledge-cell-label">版本</span>
                  <span className="knowledge-cell-value">{article.version}</span>
                </div>
                <div>
                  <span className="knowledge-cell-label">片段</span>
                  <span className="knowledge-cell-value">{article.chunkCount} chunks</span>
                </div>
                <div>
                  <span className="knowledge-cell-label">状态</span>
                  <Tag color={article.status === 'ACTIVE' ? 'green' : 'gold'}>
                    {article.status === 'ACTIVE' ? '已生效' : '索引中'}
                  </Tag>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  )
}

function QualityView({ metrics }: { metrics: Metrics }) {
  const evaluationRows = [
    ['检索基线 2026-07-A', '48', '向量 Top 3', '88.6%', '82.1%', '1.24s', '通过'],
    ['混合检索候选', '48', 'RRF + 重排序', '91.7%', '86.4%', '1.79s', '观察'],
    ['无答案专项集', '17', '阈值 + 拒答', '82.4%', '79.8%', '1.31s', '通过'],
    ['错误码专项集', '14', 'BM25 + 向量', '92.9%', '90.3%', '1.08s', '通过'],
  ]

  return (
    <div className="view-enter">
      <section className="quality-panel">
        <div className="quality-hero">
          <div className="quality-hero-item">
            <span className="quality-hero-label">Hit Rate@3</span>
            <span className="quality-hero-value">{(metrics.evaluation.hitRateAt3 * 100).toFixed(1)}%</span>
            <span className="quality-hero-note">较基线上升 3.8%</span>
          </div>
          <div className="quality-hero-item">
            <span className="quality-hero-label">MRR</span>
            <span className="quality-hero-value">{metrics.evaluation.mrr.toFixed(3)}</span>
            <span className="quality-hero-note">首条证据排名稳定</span>
          </div>
          <div className="quality-hero-item">
            <span className="quality-hero-label">证据忠实度</span>
            <span className="quality-hero-value">{(metrics.evaluation.groundedness * 100).toFixed(1)}%</span>
            <span className="quality-hero-note">评估集 96 条回答</span>
          </div>
          <div className="quality-hero-item">
            <span className="quality-hero-label">引用准确率</span>
            <span className="quality-hero-value">{(metrics.evaluation.citationAccuracy * 100).toFixed(1)}%</span>
            <span className="quality-hero-note">人工抽检 63 条引用</span>
          </div>
        </div>
        <div className="panel-header">
          <div className="panel-heading">
            <h2 className="panel-title">评估运行</h2>
            <div className="panel-meta">最近 4 次离线评估结果</div>
          </div>
        </div>
        <div className="evaluation-table-wrap">
          <table className="evaluation-table">
            <thead>
              <tr>
                <th>评估集</th>
                <th className="numeric">样本</th>
                <th>检索策略</th>
                <th className="numeric">Hit@3</th>
                <th className="numeric">MRR</th>
                <th className="numeric">p95</th>
                <th>门禁</th>
              </tr>
            </thead>
            <tbody>
              {evaluationRows.map((row) => (
                <tr key={row[0]}>
                  {row.map((cell, index) => (
                    <td className={[1, 3, 4, 5].includes(index) ? 'numeric' : ''} key={`${row[0]}-${cell}`}>
                      {index === 6 ? <Tag color={cell === '通过' ? 'green' : 'gold'}>{cell}</Tag> : cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function App() {
  const [view, setView] = useState<ViewKey>('workbench')
  const [tickets, setTickets] = useState<Ticket[]>(demoTickets)
  const [metrics, setMetrics] = useState<Metrics>(demoMetrics)
  const [selectedTicketId, setSelectedTicketId] = useState(demoTickets[0].id)
  const [apiState, setApiState] = useState<'connecting' | 'connected' | 'demo'>('connecting')
  const [analyzingTicketId, setAnalyzingTicketId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<number | null>(null)

  const selectedTicket =
    tickets.find((ticket) => ticket.id === selectedTicketId) ?? tickets[0] ?? demoTickets[0]

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([fetchTickets(controller.signal), fetchMetrics(controller.signal)])
      .then(([ticketData, metricData]) => {
        if (ticketData.length > 0) {
          setTickets(ticketData)
          setSelectedTicketId((current) =>
            ticketData.some((ticket) => ticket.id === current) ? current : ticketData[0].id,
          )
        }
        setMetrics(metricData)
        setApiState('connected')
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) return
        setApiState('demo')
      })

    return () => controller.abort()
  }, [])

  useEffect(() => {
    return () => {
      if (toastTimer.current != null) window.clearTimeout(toastTimer.current)
    }
  }, [])

  const showToast = (message: string) => {
    setToast(message)
    if (toastTimer.current != null) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 3200)
  }

  const runAnalysis = async () => {
    setAnalyzingTicketId(selectedTicket.id)
    try {
      const result = await analyzeTicket(selectedTicket.id)
      setTickets((current) =>
        current.map((ticket) =>
          ticket.id === selectedTicket.id
            ? {
                ...ticket,
                latestAnalysis: result,
                status: result.decision.escalationRequired
                  ? 'NEEDS_ESCALATION'
                  : 'READY_FOR_REVIEW',
                updatedAt: new Date().toISOString(),
              }
            : ticket,
        ),
      )
      setApiState('connected')
      showToast('分析完成，分类、证据和回复建议已更新')
    } catch (error: unknown) {
      console.warn('Ticket analysis request failed; using demo result.', error)
      await new Promise((resolve) => window.setTimeout(resolve, 1100))
      const result = createDemoAnalysis(selectedTicket)
      setTickets((current) =>
        current.map((ticket) =>
          ticket.id === selectedTicket.id
            ? {
                ...ticket,
                latestAnalysis: result,
                status: result.decision.escalationRequired
                  ? 'NEEDS_ESCALATION'
                  : 'READY_FOR_REVIEW',
                updatedAt: new Date().toISOString(),
              }
            : ticket,
        ),
      )
      setApiState('demo')
      showToast('已使用演示分析结果，启动后端后可切换到服务模式')
    } finally {
      setAnalyzingTicketId(null)
    }
  }

  const assignSelectedTicket = async () => {
    const assigneeName = '演示管理员'
    setTickets((current) =>
      current.map((ticket) =>
        ticket.id === selectedTicket.id
          ? { ...ticket, assigneeName, updatedAt: new Date().toISOString() }
          : ticket,
      ),
    )
    try {
      const updated = await updateTicket(selectedTicket.id, { assigneeName })
      setTickets((current) =>
        current.map((ticket) => (ticket.id === updated.id ? updated : ticket)),
      )
      showToast('工单已分配给演示管理员')
    } catch {
      showToast('已在演示数据中更新负责人')
    }
  }

  const currentCopy = viewCopy[view]

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#16775f',
          colorText: '#344039',
          colorTextSecondary: '#68736d',
          colorBorder: '#d9ded9',
          colorBgContainer: '#fffefa',
          borderRadius: 6,
          fontFamily: "Aptos, 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
          controlHeight: 34,
        },
      }}
    >
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <span className="brand-mark">SC</span>
            <span>
              <span className="brand-name">Support Copilot</span>
              <span className="brand-context">服务运营控制台</span>
            </span>
          </div>
          <div className="nav-section-label">工作区</div>
          <nav className="nav-list" aria-label="主导航">
            {navigation.map((item) => {
              const Icon = item.icon
              return (
                <button
                  className={`nav-item ${view === item.key ? 'active' : ''}`}
                  type="button"
                  key={item.key}
                  onClick={() => setView(item.key)}
                >
                  <Icon />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>
          <div className="sidebar-footer">
            <div className="service-state">
              <div className="service-state-row">
                <span className={`service-state-dot ${apiState === 'connected' ? '' : 'demo'}`} />
                <span>
                  {apiState === 'connected'
                    ? '业务 API 已连接'
                    : apiState === 'connecting'
                      ? '正在检查服务'
                      : '演示数据模式'}
                </span>
              </div>
              <small>
                {apiState === 'connected'
                  ? '工单与指标来自本地服务'
                  : '无需 API Key 也可审查完整界面'}
              </small>
            </div>
          </div>
        </aside>

        <div className="app-body">
          <header className="topbar">
            <div>
              <h1 className="page-title">{currentCopy.title}</h1>
              <p className="page-subtitle">{currentCopy.subtitle}</p>
            </div>
            <div className="topbar-actions">
              <button className="user-menu" type="button" onClick={() => showToast('当前为面试演示账号')}>
                <span className="user-avatar">CY</span>
                <span className="user-name">演示管理员</span>
                <ChevronDown size={13} />
              </button>
            </div>
          </header>

          <nav className="mobile-nav" aria-label="移动端导航">
            {navigation.map((item) => {
              const Icon = item.icon
              return (
                <button
                  className={`nav-item ${view === item.key ? 'active' : ''}`}
                  type="button"
                  key={item.key}
                  onClick={() => setView(item.key)}
                >
                  <Icon />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>

          <main className="page-content" id="main-content">
            {view === 'workbench' && (
              <WorkbenchView
                tickets={tickets}
                selectedTicket={selectedTicket}
                metrics={metrics}
                analyzing={analyzingTicketId === selectedTicket.id}
                onSelect={setSelectedTicketId}
                onAnalyze={runAnalysis}
                onAssign={assignSelectedTicket}
                onToast={showToast}
              />
            )}
            {view === 'overview' && <OverviewView metrics={metrics} tickets={tickets} />}
            {view === 'knowledge' && <KnowledgeView articles={demoKnowledgeArticles} />}
            {view === 'quality' && <QualityView metrics={metrics} />}
          </main>
        </div>
      </div>

      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 />
          <span>{toast}</span>
        </div>
      )}
    </ConfigProvider>
  )
}

export default App
