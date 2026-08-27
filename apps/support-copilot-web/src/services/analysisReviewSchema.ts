import * as z from 'zod'

const nonEmptyString = z.string().min(1)
const timestamp = z.iso.datetime({ offset: true })
const sharedReviewFields = {
  id: nonEmptyString,
  ticketId: nonEmptyString,
  analysisId: nonEmptyString,
  reviewerType: z.enum(['UNAUTHENTICATED_DEMO', 'AUTHENTICATED_JWT']),
  reviewerLabel: nonEmptyString,
  originalReplyContent: nonEmptyString,
  ticketVersion: z.number().int().nonnegative(),
  traceId: nonEmptyString,
  createdAt: timestamp,
}

const acceptedReviewSchema = z.strictObject({
  ...sharedReviewFields,
  action: z.enum(['APPROVED', 'EDITED']),
  reviewedReplyContent: nonEmptyString,
  reason: z.null(),
})

const rejectedReviewSchema = z.strictObject({
  ...sharedReviewFields,
  action: z.literal('REJECTED'),
  reviewedReplyContent: z.null(),
  reason: nonEmptyString.max(1000),
})

export const analysisReviewSchema = z.discriminatedUnion('action', [
  acceptedReviewSchema,
  rejectedReviewSchema,
])

export const analysisReviewListSchema = z.array(analysisReviewSchema)
