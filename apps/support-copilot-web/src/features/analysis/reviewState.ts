import type { AnalysisReview, Ticket, TicketEvent } from '../../types'

const reviewEventDetails: Record<AnalysisReview['action'], string> = {
  APPROVED: '未认证演示用户已采纳原始回复建议',
  EDITED: '未认证演示用户已编辑并采纳回复建议',
  REJECTED: '未认证演示用户已拒绝回复建议',
}

export function applyAnalysisReview(ticket: Ticket, review: AnalysisReview): Ticket {
  if (ticket.id !== review.ticketId) return ticket

  const reviewEvent: TicketEvent = {
    id: review.id,
    label: '人工审核已记录',
    detail:
      review.action === 'REJECTED'
        ? `${reviewEventDetails[review.action]}：${review.reason}`
        : reviewEventDetails[review.action],
    createdAt: review.createdAt,
  }

  return {
    ...ticket,
    latestReview: review,
    events: [...ticket.events.filter((event) => !event.id.startsWith('review-')), reviewEvent],
  }
}
