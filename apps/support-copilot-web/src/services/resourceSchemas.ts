import * as z from 'zod'

const nonEmptyString = z.string().min(1)
const timestamp = z.iso.datetime({ offset: true })

export const knowledgeHitSchema = z.strictObject({
  chunkId: nonEmptyString,
  documentTitle: nonEmptyString,
  section: nonEmptyString,
  content: nonEmptyString,
  documentType: nonEmptyString,
  score: z.number().finite().min(0).max(1),
})
export const knowledgeHitListSchema = z.array(knowledgeHitSchema)

export const knowledgeReleaseSchema = z.strictObject({
  releaseId: nonEmptyString,
  releaseVersion: z.number().int().positive(),
  corpusChecksum: z.string().regex(/^[a-f0-9]{64}$/),
  allowedScopes: z.array(z.enum(['GENERAL', 'BILLING', 'ACCOUNT', 'PRIVACY', 'TECHNICAL'])),
  status: z.enum(['DRAFT', 'APPROVED', 'PUBLISHED', 'ARCHIVED']),
  createdBy: nonEmptyString,
  createdAt: timestamp,
  approvedBy: nonEmptyString.nullable(),
  approvedAt: timestamp.nullable(),
  publishedBy: nonEmptyString.nullable(),
  publishedAt: timestamp.nullable(),
  version: z.number().int().nonnegative(),
})
export const knowledgeReleaseListSchema = z.array(knowledgeReleaseSchema)

const ticketMetadataSchema = z.strictObject({
  changedFields: z.array(z.enum(['STATUS', 'PRIORITY', 'CATEGORY', 'ASSIGNEE', 'CREATED'])),
})
const analysisMetadataSchema = z.strictObject({
  mode: z.enum(['FALLBACK', 'LIVE', 'MOCK']),
  status: z.enum(['FALLBACK', 'SUCCEEDED']),
  fallbackCategory: z.string().nullable(),
  sourceVersion: z.number().int().nonnegative(),
  resultId: nonEmptyString,
})
const reviewMetadataSchema = z.strictObject({
  reviewAction: z.enum(['APPROVED', 'EDITED', 'REJECTED']),
  sourceVersion: z.number().int().nonnegative(),
  resultId: nonEmptyString,
})
const releaseMetadataSchema = z.strictObject({
  releaseId: nonEmptyString,
  releaseVersion: z.number().int().positive(),
  corpusChecksum: z.string().regex(/^[a-f0-9]{64}$/),
  allowedScopes: z.array(z.string()),
  status: z.enum(['DRAFT', 'APPROVED', 'PUBLISHED', 'ARCHIVED']),
})

export const auditMetadataSchema = z.union([
  z.strictObject({}), ticketMetadataSchema, analysisMetadataSchema, reviewMetadataSchema,
  releaseMetadataSchema,
])
export const auditEventSchema = z.strictObject({
  id: nonEmptyString,
  actorSubject: nonEmptyString,
  actorType: nonEmptyString,
  actorRoles: z.array(nonEmptyString),
  action: z.enum([
    'TICKET_CREATED', 'TICKET_UPDATED', 'TICKET_UNASSIGNED', 'ANALYSIS_PERSISTED',
    'ANALYSIS_REVIEW_APPROVED', 'ANALYSIS_REVIEW_EDITED', 'ANALYSIS_REVIEW_REJECTED',
    'KNOWLEDGE_RELEASE_DRAFT_CREATED', 'KNOWLEDGE_RELEASE_APPROVED',
    'KNOWLEDGE_RELEASE_PUBLISHED', 'KNOWLEDGE_RELEASE_ROLLED_BACK',
  ]),
  targetType: z.enum(['TICKET', 'ANALYSIS', 'ANALYSIS_REVIEW', 'KNOWLEDGE_RELEASE']),
  targetId: nonEmptyString,
  targetVersion: z.number().int().nonnegative().nullable(),
  traceId: nonEmptyString,
  createdAt: timestamp,
  metadata: auditMetadataSchema,
})
export const auditEventPageSchema = z.strictObject({
  items: z.array(auditEventSchema),
  nextCursor: z.string().min(1).nullable(),
})

export type KnowledgeHit = z.infer<typeof knowledgeHitSchema>
export type KnowledgeRelease = z.infer<typeof knowledgeReleaseSchema>
export type AuditEvent = z.infer<typeof auditEventSchema>
export type AuditEventPage = z.infer<typeof auditEventPageSchema>
