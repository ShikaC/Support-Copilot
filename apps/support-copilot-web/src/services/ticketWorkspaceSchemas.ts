import * as z from 'zod'

export const createTicketSchema = z.strictObject({
  subject: z.string().trim().min(1, '请输入工单标题').max(240),
  customerName: z.string().trim().min(1, '请输入联系人').max(80),
  customerCompany: z.string().trim().min(1, '请输入客户企业').max(120),
  description: z.string().trim().min(1, '请描述客户问题').max(4000),
  channel: z.enum(['EMAIL', 'CHAT', 'WEB_FORM', 'PHONE']),
  customerTier: z.enum(['STANDARD', 'PREMIUM', 'ENTERPRISE']),
  language: z.string().max(16).default('zh-CN'),
})
export type CreateTicketInput = z.infer<typeof createTicketSchema>
export const ticketNoteSchema = z.strictObject({
  id: z.string().min(1), ticketId: z.string().min(1), content: z.string().min(1),
  authorLabel: z.string().min(1), createdAt: z.iso.datetime({ offset: true }),
})
export const ticketNotesSchema = z.array(ticketNoteSchema)
export type TicketNote = z.infer<typeof ticketNoteSchema>
export type TicketQueueQuery = {
  readonly keyword?: string
  readonly status?: string
  readonly priority?: string
  readonly sort?: 'NEWEST' | 'SLA' | 'PRIORITY'
  readonly assignee?: string
  readonly limit?: string
  readonly cursor?: string
}

export const pendingTicketQuery: TicketQueueQuery = { status: 'NEW,READY_FOR_REVIEW,READY_FOR_MANUAL_REVIEW,NEEDS_ESCALATION,IN_PROGRESS,WAITING_CUSTOMER' }

export const ticketActivitySchema = z.strictObject({ items: z.array(z.strictObject({ id:z.string().min(1), action:z.string().min(1), actorLabel:z.string().min(1), createdAt:z.iso.datetime({offset:true}), traceId:z.string().min(1), ticketVersion:z.number().int().nonnegative().nullable(), detail:z.string().min(1) })), nextCursor:z.string().nullable() })
export type TicketActivityPage = z.infer<typeof ticketActivitySchema>
