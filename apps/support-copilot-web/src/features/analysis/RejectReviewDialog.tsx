import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react'
import { Alert, Input, Modal } from 'antd'

type RejectReviewDialogProps = {
  readonly open: boolean
  readonly confirming: boolean
  readonly errorMessage: string | null
  readonly returnFocusRef: RefObject<HTMLButtonElement | null>
  readonly onCancel: () => void
  readonly onConfirm: (reason: string) => void
}

export function RejectReviewDialog({
  open,
  confirming,
  errorMessage,
  returnFocusRef,
  onCancel,
  onConfirm,
}: RejectReviewDialogProps) {
  const [reason, setReason] = useState('')
  const modalContentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) setReason('')
  }, [open])

  const normalizedReason = reason.trim()
  const cancel = () => {
    if (confirming) return
    onCancel()
    queueMicrotask(() => returnFocusRef.current?.focus())
  }
  const trapFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      cancel()
      return
    }
    if (event.key !== 'Tab') return
    const focusable = [...(modalContentRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])') ?? [])]
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (first === undefined || last === undefined) return
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <Modal
      title="拒绝回复建议"
      open={open}
      okText="确认拒绝"
      cancelText="取消"
      okButtonProps={{ danger: true, disabled: !normalizedReason }}
      confirmLoading={confirming}
      closable={!confirming}
      keyboard={false}
      mask={{ closable: !confirming }}
      destroyOnHidden
      modalRender={(modal) => <div ref={modalContentRef} onKeyDown={trapFocus}>{modal}</div>}
      onCancel={cancel}
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
