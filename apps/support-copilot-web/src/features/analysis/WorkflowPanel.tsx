import { Progress } from 'antd'
import { AlertTriangle, Check, Clock3, RefreshCw } from 'lucide-react'
import type { AnalysisResult } from '../../types'
import { categoryLabels, priorityLabels, sentimentLabels } from '../shared/presentationData'

export function WorkflowPanel({ analysis }: { readonly analysis: AnalysisResult }) {
  return <div className="analysis-content">
    <div className="analysis-summary">
      <div className="analysis-fact"><span className="analysis-fact-label">建议分类</span><span className="analysis-fact-value">{categoryLabels[analysis.classification.category] ?? analysis.classification.category}</span></div>
      <div className="analysis-fact"><span className="analysis-fact-label">建议优先级</span><span className="analysis-fact-value">{priorityLabels[analysis.classification.priority]}</span></div>
      <div className="analysis-fact"><span className="analysis-fact-label">客户情绪</span><span className="analysis-fact-value">{sentimentLabels[analysis.classification.sentiment]}</span></div>
      <div className="analysis-fact"><span className="analysis-fact-label">处理建议</span><span className="analysis-fact-value">{analysis.decision.escalationRequired ? '升级人工' : '一线审核'}</span></div>
    </div>
    <div className="confidence-row"><div className="confidence-copy"><span>分类置信度</span><strong>{(analysis.classification.confidence * 100).toFixed(0)}%</strong></div>
      <Progress percent={analysis.classification.confidence * 100} showInfo={false} strokeColor="oklch(0.48 0.11 162)" railColor="oklch(0.92 0.008 100)" size="small" />
    </div>
    <div className="analysis-reason">{analysis.classification.reasonSummary}</div>
    <div className="section-heading-row"><h3 className="section-label">处理轨迹</h3><span className={`mode-badge ${analysis.mode}`}>{analysis.mode === 'live' ? 'LIVE' : analysis.mode === 'mock' ? 'DEMO' : 'FALLBACK'}</span></div>
    <div className="workflow-list">{analysis.workflowSteps.map((step) => <div className="workflow-step" key={step.id}>
      <span className={`step-icon ${step.status}`}>{step.status === 'complete' ? <Check size={13} /> : step.status === 'running' ? <RefreshCw size={13} /> : step.status === 'failed' ? <AlertTriangle size={13} /> : <Clock3 size={13} />}</span>
      <div><div className="step-name">{step.name}</div><div className="step-description">{step.description}</div></div>
      <span className="step-duration">{step.durationMs == null ? '等待' : `${step.durationMs} ms`}</span>
    </div>)}</div>
    <div className="trace-meta"><span>{analysis.traceId}</span><span>{analysis.promptVersion}</span></div>
  </div>
}
