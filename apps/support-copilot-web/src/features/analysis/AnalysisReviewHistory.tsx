import { Check, Pencil, XCircle } from 'lucide-react'
import { Empty, Spin } from 'antd'

import type { AnalysisReview } from '../../types'

type AnalysisReviewHistoryProps = {
  readonly reviews: readonly AnalysisReview[]
  readonly loading: boolean
  readonly errorMessage: string | null
}

const reviewLabels: Record<AnalysisReview['action'], string> = {
  APPROVED: '采纳原建议',
  EDITED: '编辑后采纳',
  REJECTED: '拒绝建议',
}

function ReviewIcon({ action }: { readonly action: AnalysisReview['action'] }) {
  if (action === 'REJECTED') return <XCircle aria-hidden="true" />
  if (action === 'EDITED') return <Pencil aria-hidden="true" />
  return <Check aria-hidden="true" />
}

export function AnalysisReviewHistory({
  reviews,
  loading,
  errorMessage,
}: AnalysisReviewHistoryProps) {
  return (
    <section className="review-history" aria-label="审核历史">
      <div className="review-history-heading">审核历史</div>
      {loading ? (
        <div className="review-history-loading">
          <Spin size="small" />
        </div>
      ) : errorMessage ? (
        <div className="review-history-error" role="alert">
          {errorMessage}
        </div>
      ) : reviews.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无审核记录" />
      ) : (
        <div className="review-history-list">
          {reviews.map((review) => (
            <article className={`review-history-item is-${review.action.toLowerCase()}`} key={review.id}>
              <ReviewIcon action={review.action} />
              <div>
                <div className="review-history-meta">
                  <strong>{reviewLabels[review.action]}</strong>
                  <span>{new Date(review.createdAt).toLocaleString('zh-CN', { hour12: false })}</span>
                </div>
                <p>
                  {review.action === 'REJECTED'
                    ? review.reason
                    : `${review.reviewerLabel}（未认证演示身份）`}
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
