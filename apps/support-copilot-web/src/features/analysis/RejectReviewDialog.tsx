import { useEffect, useState } from 'react'
import { Alert, Input, Modal } from 'antd'

type RejectReviewDialogProps = {
  readonly open: boolean
  readonly confirming: boolean
  readonly errorMessage: string | null
  readonly onCancel: () => void
  readonly onConfirm: (reason: string) => void
}

export function RejectReviewDialog({
  open,
  confirming,
  errorMessage,
  onCancel,
  onConfirm,
}: RejectReviewDialogProps) {
  const [reason, setReason] = useState('')

  useEffect(() => {
    if (!open) setReason('')
  }, [open])

  const normalizedReason = reason.trim()

  return (
    <Modal
      title="拒绝回复建议"
      open={open}
      okText="确认拒绝"
      cancelText="取消"
      okButtonProps={{ danger: true, disabled: !normalizedReason }}
      confirmLoading={confirming}
      closable={!confirming}
      maskClosable={!confirming}
      onCancel={onCancel}
      onOk={() => onConfirm(normalizedReason)}
    >
      <label className="reject-reason-label" htmlFor="reject-review-reason">
        拒绝原因
      </label>
      <Input.TextArea
        id="reject-review-reason"
        autoFocus
        rows={4}
        maxLength={1000}
        showCount
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      {errorMessage && <Alert className="reject-review-error" type="error" showIcon message={errorMessage} />}
    </Modal>
  )
}
