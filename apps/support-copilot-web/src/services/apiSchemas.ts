import * as z from 'zod'

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

const nonEmptyString = z.string().min(1)
const timestamp = z.iso.datetime({ offset: true })
export const prioritySchema = z.enum(['LOW', 'MEDIUM', 'HIGH', 'URGENT'])
export const analysisModeSchema = z.enum(['live', 'mock', 'fallback'])
export const fallbackReasonSchema = z.enum(FALLBACK_REASONS)

export const workflowStepSchema = z.strictObject({
  id: nonEmptyString,
  name: nonEmptyString,
  description: z.string(),
  status: z.enum(['complete', 'running', 'pending', 'failed']),
  durationMs: z.number().int().nonnegative().nullable().optional(),
})

export const retrievalHitSchema = z.strictObject({
  chunkId: nonEmptyString,
  documentId: nonEmptyString,
  documentTitle: nonEmptyString,
  section: nonEmptyString,
  content: nonEmptyString,
  sourceUri: nonEmptyString,
  retrievalMethod: nonEmptyString,
  initialRank: z.number().int().nonnegative(),
  initialScore: z.number().finite(),
  rerankPosition: z.number().int().nonnegative(),
  rerankScore: z.number().finite(),
  usedAsEvidence: z.boolean(),
})

export const analysisResultSchema = z
  .strictObject({
    id: nonEmptyString,
    traceId: nonEmptyString,
    status: z.enum(['SUCCEEDED', 'FALLBACK']),
    mode: analysisModeSchema,
    fallbackReason: fallbackReasonSchema.nullable(),
    modelName: nonEmptyString,
    promptVersion: nonEmptyString,
    classification: z.strictObject({
      intent: nonEmptyString,
      category: nonEmptyString,
      priority: prioritySchema,
      sentiment: z.enum(['POSITIVE', 'NEUTRAL', 'NEGATIVE']),
      confidence: z.number().min(0).max(1),
      reasonSummary: nonEmptyString,
    }),
    workflowSteps: z.array(workflowStepSchema),
    retrieval: z.strictObject({
      query: z.string(),
      hits: z.array(retrievalHitSchema),
    }),
    suggestedReply: z.strictObject({
      content: nonEmptyString,
      citations: z.array(z.string()),
      warnings: z.array(z.string()),
    }),
    decision: z.strictObject({
      escalationRequired: z.boolean(),
      reason: nonEmptyString,
    }),
    usage: z.strictObject({
      inputTokens: z.number().int().nonnegative(),
      outputTokens: z.number().int().nonnegative(),
      durationMs: z.number().int().nonnegative(),
    }),
    createdAt: timestamp,
  })
  .superRefine((analysis, context) => {
    const mode = analysis.mode
    switch (mode) {
      case 'live':
      case 'mock':
        if (analysis.status !== 'SUCCEEDED') {
          context.addIssue({
            code: 'custom',
            path: ['status'],
            message: `${mode} analysis must be SUCCEEDED`,
          })
        }
        if (analysis.fallbackReason !== null) {
          context.addIssue({
            code: 'custom',
            path: ['fallbackReason'],
            message: `${mode} analysis cannot have a fallback reason`,
          })
        }
        return
      case 'fallback':
        if (analysis.status !== 'FALLBACK') {
          context.addIssue({
            code: 'custom',
            path: ['status'],
            message: 'fallback analysis must have FALLBACK status',
          })
        }
        if (analysis.fallbackReason === null) {
          context.addIssue({
            code: 'custom',
            path: ['fallbackReason'],
            message: 'fallback analysis must have a reason',
          })
        }
        return
      default: {
        const unreachable: never = mode
        return unreachable
      }
    }
  })

export const ticketEventSchema = z.strictObject({
  id: nonEmptyString,
  label: nonEmptyString,
  detail: z.string(),
  createdAt: timestamp,
})

export const ticketResponseSchema = z.strictObject({
  id: nonEmptyString,
  ticketNo: nonEmptyString,
  channel: z.enum(['EMAIL', 'CHAT', 'WEB_FORM', 'PHONE']),
  customerName: nonEmptyString,
  customerCompany: nonEmptyString,
  customerTier: z.enum(['STANDARD', 'PREMIUM', 'ENTERPRISE']),
  subject: nonEmptyString,
  description: nonEmptyString,
  language: nonEmptyString,
  category: nonEmptyString,
  priority: prioritySchema,
  status: z.enum([
    'NEW',
    'ANALYZING',
    'READY_FOR_REVIEW',
    'IN_PROGRESS',
    'NEEDS_ESCALATION',
    'WAITING_CUSTOMER',
    'RESOLVED',
    'CLOSED',
    'READY_FOR_MANUAL_REVIEW',
  ]),
  assigneeName: z.string().nullable(),
  slaDeadline: timestamp,
  createdAt: timestamp,
  updatedAt: timestamp,
  version: z.number().int().nonnegative(),
  latestAnalysis: analysisResultSchema.nullable(),
  events: z.array(ticketEventSchema),
})

export const ticketResponseListSchema = z.array(ticketResponseSchema)

const rate = z.number().min(0).max(1)

export const metricsResponseSchema = z.strictObject({
  summary: z.strictObject({
    openTickets: z.number().int().nonnegative(),
    urgentTickets: z.number().int().nonnegative(),
    slaRiskTickets: z.number().int().nonnegative(),
    analysisSuccessRate: rate,
  }),
  ticketTrend: z.array(
    z.strictObject({
      date: nonEmptyString,
      created: z.number().int().nonnegative(),
      resolved: z.number().int().nonnegative(),
    }),
  ),
  categoryDistribution: z.array(
    z.strictObject({
      category: nonEmptyString,
      count: z.number().int().nonnegative(),
    }),
  ),
  analysisLatency: z.strictObject({
    averageMs: z.number().int().nonnegative(),
    p95Ms: z.number().int().nonnegative(),
  }),
  suggestionAcceptanceRate: rate,
  evaluation: z.strictObject({
    hitRateAt3: rate,
    mrr: rate,
    groundedness: rate,
    citationAccuracy: rate,
  }),
})
