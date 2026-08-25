import type * as z from 'zod'

import type {
  analysisModeSchema,
  analysisResultSchema,
  fallbackReasonSchema,
  metricsResponseSchema,
  prioritySchema,
  retrievalHitSchema,
  ticketEventSchema,
  ticketResponseSchema,
  workflowStepSchema,
} from './services/apiSchemas'

export { FALLBACK_REASONS } from './services/apiSchemas'

export type AnalysisMode = z.infer<typeof analysisModeSchema>
export type AnalysisResult = z.infer<typeof analysisResultSchema>
export type FallbackReason = z.infer<typeof fallbackReasonSchema>
export type Metrics = z.infer<typeof metricsResponseSchema>
export type Priority = z.infer<typeof prioritySchema>
export type RetrievalHit = z.infer<typeof retrievalHitSchema>
export type TicketEvent = z.infer<typeof ticketEventSchema>
export type WorkflowStep = z.infer<typeof workflowStepSchema>

type ApiTicket = z.infer<typeof ticketResponseSchema>

export type TicketStatus = ApiTicket['status']

export type Ticket = Omit<ApiTicket, 'latestAnalysis' | 'version'> & {
  latestAnalysis?: ApiTicket['latestAnalysis']
  version?: ApiTicket['version']
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
