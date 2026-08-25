import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Link2 } from 'lucide-react'
import { Button, Input } from 'antd'

import { ApiError, reviewAnalysisReply } from '../../services/api'
import type { AnalysisResult, AnalysisReview, Ticket } from '../../types'

type ReplyReviewProps = {
  readonly ticket: Ticket
  readonly analysis: AnalysisResult
  readonly onReviewSaved: (review: AnalysisReview) => void
  readonly onToast: (message: string, kind?: 'success' | 'error') => void
}

const reviewLabels: Record<AnalysisReview['action'], string> = {
  APPROVED: '原建议已采纳',
  EDITED: '编辑后已采纳',
}

const reviewToastMessages: Record<AnalysisReview['action'], string> = {
  APPROVED: '回复建议审核已记录',
  EDITED: '修改后的回复审核已记录',
}

function matchingReview(analysis: AnalysisResult, review: AnalysisReview | null) {
  return review?.analysisId === analysis.id ? review : null
}

function reviewedReply(analysis: AnalysisResult, review: AnalysisReview | null) {
  return matchingReview(analysis, review)?.reviewedReplyContent ?? analysis.suggestedReply.content
}

export function ReplyReview({ ticket, analysis, onReviewSaved, onToast }: ReplyReviewProps) {
  const initialReview = matchingReview(analysis, ticket.latestReview ?? null)
  const [reply, setReply] = useState(() => reviewedReply(analysis, initialReview))
  const [review, setReview] = useState<AnalysisReview | null>(initialReview)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const reviewKey = `${ticket.id}:${analysis.id}`
  const activeReviewKey = useRef(reviewKey)
  activeReviewKey.current = reviewKey

  useEffect(() => {
    const latestReview = matchingReview(analysis, ticket.latestReview ?? null)
    setReply(reviewedReply(analysis, latestReview))
    setReview(latestReview)
    setSubmitting(false)
    setErrorMessage(null)
  }, [analysis, ticket.latestReview])

  const normalizedReply = reply.trim()
  const persistenceAvailable = ticket.version != null
  const currentReview = matchingReview(analysis, review)
  const reviewIsCurrent = currentReview?.reviewedReplyContent === normalizedReply

  const submitReview = async () => {
    if (!persistenceAvailable || !normalizedReply || submitting || reviewIsCurrent) return

    const requestReviewKey = reviewKey
    setSubmitting(true)
    setErrorMessage(null)
    try {
      const savedReview = await reviewAnalysisReply(ticket.id, analysis.id, normalizedReply)
      onReviewSaved(savedReview)
      if (activeReviewKey.current !== requestReviewKey) return
      setReview(savedReview)
      onToast(reviewToastMessages[savedReview.action])
    } catch (error: unknown) {
      if (activeReviewKey.current !== requestReviewKey) return
      const message =
        error instanceof ApiError
          ? error.code === 'ANALYSIS_REVIEW_STALE'
            ? '工单或分析已更新，请刷新后重新审核'
            : error.message
          : '服务不可用，审核记录未保存'
      setErrorMessage(message)
      onToast(message, 'error')
    } finally {
      if (activeReviewKey.current === requestReviewKey) setSubmitting(false)
    }
  }

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

      {errorMessage && (
        <div className="reply-error" role="alert">
          <AlertTriangle />
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="reply-footer">
        <span className="reply-usage" id="reply-review-status">
          {!persistenceAvailable
            ? '演示数据 · 不保存审核记录'
            : currentReview
              ? reviewIsCurrent
                ? `${reviewLabels[currentReview.action]} · ${currentReview.reviewerLabel}（未认证演示身份）`
                : '当前修改尚未记录'
              : `${analysis.usage.inputTokens + analysis.usage.outputTokens} tokens · ${(
                  analysis.usage.durationMs / 1000
                ).toFixed(2)} s`}
        </span>
        <Button
          type="primary"
          icon={<Check size={13} />}
          loading={submitting}
          aria-describedby={!persistenceAvailable ? 'reply-review-status' : undefined}
          disabled={submitting || !persistenceAvailable || !normalizedReply || reviewIsCurrent}
          onClick={submitReview}
        >
          {reviewIsCurrent ? '审核已记录' : currentReview ? '更新审核' : '记录审核'}
        </Button>
      </div>
    </div>
  )
}
