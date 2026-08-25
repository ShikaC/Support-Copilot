export type TicketStatus =
  | 'NEW'
  | 'ANALYZING'
  | 'READY_FOR_REVIEW'
  | 'IN_PROGRESS'
  | 'NEEDS_ESCALATION'
  | 'WAITING_CUSTOMER'
  | 'RESOLVED'
  | 'CLOSED'
  | 'READY_FOR_MANUAL_REVIEW'

export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'

export type AnalysisMode = 'live' | 'mock' | 'fallback'

export const FALLBACK_REASONS = [
  'insufficient_evidence',
  'embedding_api_error',
  'embedding_connection_timeout',
  'embedding_response_timeout',
  'structured_generation_api_error',
  'structured_generation_connection_timeout',
  'structured_generation_response_timeout',
  'invalid_model_response',
  'processing_timeout',
  'ai_service_timeout',
  'ai_service_unavailable',
  'ai_service_error',
  'invalid_ai_response',
] as const

export type FallbackReason = (typeof FALLBACK_REASONS)[number]

export interface WorkflowStep {
  id: string
  name: string
  description: string
  status: 'complete' | 'running' | 'pending' | 'failed'
  durationMs?: number
}

export interface RetrievalHit {
  chunkId: string
  documentId: string
  documentTitle: string
  section: string
  content: string
  sourceUri: string
  retrievalMethod: string
  initialRank: number
  initialScore: number
  rerankPosition: number
  rerankScore: number
  usedAsEvidence: boolean
}

export interface AnalysisResult {
  id: string
  traceId: string
  status: 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'FALLBACK'
  mode: AnalysisMode
  fallbackReason: FallbackReason | null
  modelName: string
  promptVersion: string
  classification: {
    intent: string
    category: string
    priority: Priority
    sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE'
    confidence: number
    reasonSummary: string
  }
  workflowSteps: WorkflowStep[]
  retrieval: {
    query: string
    hits: RetrievalHit[]
  }
  suggestedReply: {
    content: string
    citations: string[]
    warnings: string[]
  }
  decision: {
    escalationRequired: boolean
    reason: string
  }
  usage: {
    inputTokens: number
    outputTokens: number
    durationMs: number
  }
  createdAt: string
}

export interface TicketEvent {
  id: string
  label: string
  detail: string
  createdAt: string
}

export interface Ticket {
  id: string
  ticketNo: string
  channel: 'EMAIL' | 'CHAT' | 'WEB_FORM' | 'PHONE'
  customerName: string
  customerCompany: string
  customerTier: 'STANDARD' | 'PREMIUM' | 'ENTERPRISE'
  subject: string
  description: string
  language: string
  category: string
  priority: Priority
  status: TicketStatus
  assigneeName: string | null
  slaDeadline: string
  createdAt: string
  updatedAt: string
  version?: number
  latestAnalysis?: AnalysisResult
  events: TicketEvent[]
}

export interface Metrics {
  summary: {
    openTickets: number
    urgentTickets: number
    slaRiskTickets: number
    analysisSuccessRate: number
  }
  ticketTrend: Array<{ date: string; created: number; resolved: number }>
  categoryDistribution: Array<{ category: string; count: number }>
  analysisLatency: {
    averageMs: number
    p95Ms: number
  }
  suggestionAcceptanceRate: number
  evaluation: {
    hitRateAt3: number
    mrr: number
    groundedness: number
    citationAccuracy: number
  }
}

export interface KnowledgeArticle {
  id: string
  title: string
  documentType: 'POLICY' | 'RUNBOOK' | 'FAQ' | 'PRODUCT_GUIDE'
  version: string
  status: 'ACTIVE' | 'INDEXING' | 'ARCHIVED'
  chunkCount: number
  updatedAt: string
  owner: string
  coverage: string[]
}
