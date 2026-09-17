import { useState } from 'react'
import { Alert, Button, Form, Input, Modal, Select } from 'antd'
import type { Ticket } from '../../types'
import type { TicketUpdate } from '../../services/api'
import { categoryLabels, priorityLabels } from '../shared/presentationData'

type Props = { readonly ticket: Ticket; readonly onClose: () => void; readonly onSave: (update: TicketUpdate) => Promise<boolean> }
export function EditTicketDialog({ ticket, onClose, onSave }: Props) {
  const [openedVersion] = useState(ticket.version)
  const stale = ticket.version !== openedVersion
  const [saving, setSaving] = useState(false)
  const submit = async (value: TicketUpdate) => {
    if (stale) return
    setSaving(true)
    try { if (await onSave({ ...value, assigneeName: value.assigneeName?.trim() || undefined })) onClose() }
    finally { setSaving(false) }
  }
  return <Modal open title="编辑工单属性" onCancel={onClose} closable={!saving} maskClosable={!saving} keyboard={!saving} footer={null}>
    {stale && <Alert type="warning" showIcon title="工单已被更新，请关闭此窗口后重新编辑。当前草稿未提交。" />}
    <Form layout="vertical" initialValues={{ priority: ticket.priority, category: ticket.category, assigneeName: ticket.assigneeName }} onFinish={submit} disabled={saving || stale}>
      <Form.Item label="优先级" name="priority"><Select options={Object.entries(priorityLabels).map(([value, label]) => ({ value, label }))} /></Form.Item>
      <Form.Item label="业务分类" name="category"><Select options={Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))} /></Form.Item>
      <Form.Item label="负责人" name="assigneeName"><Input maxLength={80} placeholder="填写团队成员姓名；取消分配请使用取消负责人" /></Form.Item>
      <div className="dialog-footer"><span>更新将记录在审计日志中</span><Button type="primary" htmlType="submit" loading={saving}>保存修改</Button></div>
    </Form>
  </Modal>
}
