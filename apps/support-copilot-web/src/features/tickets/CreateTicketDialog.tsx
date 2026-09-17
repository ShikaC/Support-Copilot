import { useState } from 'react'
import { Alert, Button, Form, Input, Modal, Select } from 'antd'
import { ArrowUpRight } from 'lucide-react'
import { ApiError, ApiRequestError } from '../../services/api'
import { createTicketSchema, type CreateTicketInput } from '../../services/ticketWorkspaceSchemas'

type Props = { readonly onClose: () => void; readonly onCreate: (input: CreateTicketInput) => Promise<unknown> }
export function CreateTicketDialog({ onClose, onCreate }: Props) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submit = async (value: CreateTicketInput) => {
    const parsed = createTicketSchema.safeParse(value)
    if (!parsed.success) { setError(parsed.error.issues[0]?.message ?? '请检查输入'); return }
    setSaving(true); setError(null)
    try { await onCreate(parsed.data); onClose() }
    catch (failure: unknown) {
      setError(failure instanceof ApiError ? failure.message : failure instanceof ApiRequestError && failure.kind === 'timeout'
        ? '创建结果尚未确认。请保持表单内容不变后重试，系统会避免重复创建。' : '创建失败，请检查服务连接后重试。表单内容已保留。')
    } finally { setSaving(false) }
  }
  return <Modal open title="新建工单" onCancel={onClose} closable={!saving} maskClosable={!saving} keyboard={!saving} footer={null} width={640}>
    <p className="dialog-intro">记录客户的问题，为每一次服务建立清晰的起点。</p>
    {error && <Alert type="error" showIcon title={error} className="form-alert" />}
    <Form layout="vertical" onFinish={submit} initialValues={{ channel: 'EMAIL', customerTier: 'STANDARD', language: 'zh-CN' }} disabled={saving} requiredMark="optional">
      <Form.Item label="工单标题" name="subject" rules={[{ required: true, whitespace: true, message: '请输入工单标题' }]}><Input autoFocus maxLength={240} placeholder="简要描述客户需要解决的问题" /></Form.Item>
      <div className="form-grid"><Form.Item label="联系人" name="customerName" rules={[{ required: true, whitespace: true, message: '请输入联系人' }]}><Input maxLength={80} placeholder="客户姓名" /></Form.Item>
        <Form.Item label="客户企业" name="customerCompany" rules={[{ required: true, whitespace: true, message: '请输入客户企业' }]}><Input maxLength={120} placeholder="企业或组织名称" /></Form.Item></div>
      <div className="form-grid"><Form.Item label="来源渠道" name="channel"><Select options={[{ value: 'EMAIL', label: '邮件' }, { value: 'CHAT', label: '在线会话' }, { value: 'WEB_FORM', label: '网页表单' }, { value: 'PHONE', label: '电话' }]} /></Form.Item>
        <Form.Item label="客户等级" name="customerTier"><Select options={[{ value: 'STANDARD', label: '标准客户' }, { value: 'PREMIUM', label: '专业客户' }, { value: 'ENTERPRISE', label: '企业客户' }]} /></Form.Item></div>
      <Form.Item label="问题描述" name="description" rules={[{ required: true, whitespace: true, message: '请描述客户问题' }]}><Input.TextArea rows={5} maxLength={4000} showCount placeholder="描述问题背景、发生时间、影响范围和期望结果…" /></Form.Item>
      <div className="dialog-footer"><span>创建后可进行 AI 分析与人工处理</span><Button type="primary" htmlType="submit" loading={saving} icon={<ArrowUpRight size={15} />}>创建工单</Button></div>
    </Form>
  </Modal>
}
