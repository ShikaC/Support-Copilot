import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, History, Link2, XCircle } from 'lucide-react'
import { Button, Input, Tooltip } from 'antd'

import {
  ApiError,
  fetchAnalysisReviews,
  rejectAnalysisReply,
  reviewAnalysisReply,
} from '../../services/api'
import type { AnalysisResult, AnalysisReview, Ticket } from '../../types'
import { AnalysisReviewHistory } from './AnalysisReviewHistory'
import { RejectReviewDialog } from './RejectReviewDialog'

type ReplyReviewProps = {
  readonly ticket: Ticket
  readonly analysis: AnalysisResult
  readonly onReviewSaved: (review: AnalysisReview) => void
  readonly onToast: (message: string, kind?: 'success' | 'error') => void
}

const reviewLabels: Record<AnalysisReview['action'], string> = {
  APPROVED: '原建议已采纳',
  EDITED: '编辑后已采纳',
  REJECTED: '回复建议已拒绝',
}

const reviewToastMessages: Record<AnalysisReview['action'], string> = {
  APPROVED: '回复建议审核已记录',
  EDITED: '修改后的回复审核已记录',
  REJECTED: '回复建议拒绝记录已保存',
}

function matchingReview(analysis: AnalysisResult, review: AnalysisReview | null) {
  return review?.analysisId === analysis.id ? review : null
}

function reviewedReply(analysis: AnalysisResult, review: AnalysisReview | null) {
  return matchingReview(analysis, review)?.reviewedReplyContent ?? analysis.suggestedReply.content
}

function apiReviewErrorMessage(error: ApiError) {
  return error.code === 'ANALYSIS_REVIEW_STALE'
    ? '工单或分析已更新，请刷新后重新审核'
    : error.message
}

function reviewerCopy(review: AnalysisReview) {
  return review.reviewerType === 'UNAUTHENTICATED_DEMO'
    ? `${review.reviewerLabel}（未认证演示身份）`
    : review.reviewerLabel
}

export function ReplyReview({ ticket, analysis, onReviewSaved, onToast }: ReplyReviewProps) {
  const initialReview = matchingReview(analysis, ticket.latestReview ?? null)
  const [reply, setReply] = useState(() => reviewedReply(analysis, initialReview))
  const [review, setReview] = useState<AnalysisReview | null>(initialReview)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [rejectErrorMessage, setRejectErrorMessage] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyErrorMessage, setHistoryErrorMessage] = useState<string | null>(null)
  const [reviewHistory, setReviewHistory] = useState<AnalysisReview[]>([])
  const reviewKey = `${ticket.id}:${analysis.id}`
  const activeReviewKey = useRef(reviewKey)
  activeReviewKey.current = reviewKey

  useEffect(() => {
    const latestReview = matchingReview(analysis, ticket.latestReview ?? null)
    setReply(reviewedReply(analysis, latestReview))
    setReview(latestReview)
    setSubmitting(false)
    setErrorMessage(null)
    setRejectDialogOpen(false)
    setRejectErrorMessage(null)
    setHistoryOpen(false)
    setHistoryLoaded(false)
    setHistoryLoading(false)
    setHistoryErrorMessage(null)
    setReviewHistory([])
  }, [analysis, ticket.latestReview])

  const normalizedReply = reply.trim()
  const persistenceAvailable = ticket.version != null
  const currentReview = matchingReview(analysis, review)
  const reviewIsCurrent =
    currentReview?.action !== 'REJECTED' && currentReview?.reviewedReplyContent === normalizedReply

  const applySavedReview = (savedReview: AnalysisReview, requestReviewKey: string) => {
    onReviewSaved(savedReview)
    if (activeReviewKey.current !== requestReviewKey) return false
    setReview(savedReview)
    if (historyLoaded) {
      setReviewHistory((current) => [
        savedReview,
        ...current.filter((item) => item.id !== savedReview.id),
      ])
    }
    onToast(reviewToastMessages[savedReview.action])
    return true
  }

  const submitReview = async () => {
    if (!persistenceAvailable || !normalizedReply || submitting || reviewIsCurrent) return

    const requestReviewKey = reviewKey
    setSubmitting(true)
    setErrorMessage(null)
    try {
      const savedReview = await reviewAnalysisReply(ticket.id, analysis.id, normalizedReply)
      applySavedReview(savedReview, requestReviewKey)
    } catch (error: unknown) {
      if (activeReviewKey.current !== requestReviewKey) return
      const message =
        error instanceof ApiError ? apiReviewErrorMessage(error) : '服务不可用，审核记录未保存'
      setErrorMessage(message)
      onToast(message, 'error')
    } finally {
      if (activeReviewKey.current === requestReviewKey) setSubmitting(false)
    }
  }

  const submitRejection = async (reason: string) => {
    if (!persistenceAvailable || submitting || currentReview?.action === 'REJECTED') return

    const requestReviewKey = reviewKey
    setSubmitting(true)
    setRejectErrorMessage(null)
    try {
      const savedReview = await rejectAnalysisReply(ticket.id, analysis.id, reason)
      if (applySavedReview(savedReview, requestReviewKey)) setRejectDialogOpen(false)
    } catch (error: unknown) {
      if (activeReviewKey.current !== requestReviewKey) return
      const message =
        error instanceof ApiError ? apiReviewErrorMessage(error) : '服务不可用，审核记录未保存'
      setRejectErrorMessage(message)
      onToast(message, 'error')
    } finally {
      if (activeReviewKey.current === requestReviewKey) setSubmitting(false)
    }
  }

  const toggleHistory = async () => {
    const nextOpen = !historyOpen
    setHistoryOpen(nextOpen)
    if (!nextOpen || historyLoaded || historyLoading) return

    const requestReviewKey = reviewKey
    setHistoryLoading(true)
    setHistoryErrorMessage(null)
    try {
      const reviews = await fetchAnalysisReviews(ticket.id, analysis.id)
      if (activeReviewKey.current !== requestReviewKey) return
      setReviewHistory(reviews)
      setHistoryLoaded(true)
    } catch (error: unknown) {
      if (activeReviewKey.current !== requestReviewKey) return
      setHistoryErrorMessage(error instanceof ApiError ? error.message : '审核历史加载失败')
    } finally {
      if (activeReviewKey.current === requestReviewKey) setHistoryLoading(false)
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
              ? currentReview.action === 'REJECTED' || reviewIsCurrent
                ? `${reviewLabels[currentReview.action]} · ${reviewerCopy(currentReview)}`
                : '当前修改尚未记录'
              : `${analysis.usage.inputTokens + analysis.usage.outputTokens} tokens · ${(
                  analysis.usage.durationMs / 1000
                ).toFixed(2)} s`}
        </span>
        <div className="reply-actions">
          <Tooltip title="审核历史">
            <Button
              type="text"
              icon={<History size={15} />}
              aria-label="审核历史"
              aria-expanded={historyOpen}
              disabled={!persistenceAvailable}
              onClick={toggleHistory}
            />
          </Tooltip>
          <Button
            danger
            icon={<XCircle size={13} />}
            disabled={submitting || !persistenceAvailable || currentReview?.action === 'REJECTED'}
            onClick={() => {
              setRejectErrorMessage(null)
              setRejectDialogOpen(true)
            }}
          >
            {currentReview?.action === 'REJECTED' ? '已拒绝' : '拒绝建议'}
          </Button>
          <Button
            type="primary"
            icon={<Check size={13} />}
            loading={submitting && !rejectDialogOpen}
            aria-describedby={!persistenceAvailable ? 'reply-review-status' : undefined}
            disabled={submitting || !persistenceAvailable || !normalizedReply || reviewIsCurrent}
            onClick={submitReview}
          >
            {reviewIsCurrent ? '审核已记录' : currentReview ? '更新审核' : '记录审核'}
          </Button>
        </div>
      </div>

      {historyOpen && (
        <AnalysisReviewHistory
          reviews={reviewHistory}
          loading={historyLoading}
          errorMessage={historyErrorMessage}
        />
      )}

      <RejectReviewDialog
        open={rejectDialogOpen}
        confirming={submitting}
        errorMessage={rejectErrorMessage}
        onCancel={() => {
          if (!submitting) setRejectDialogOpen(false)
        }}
        onConfirm={submitRejection}
      />
    </div>
  )
}
