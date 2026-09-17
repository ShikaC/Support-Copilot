import { useEffect, useState } from 'react'
import { Button, Input } from 'antd'
import { LockKeyhole, Send } from 'lucide-react'
import { ApiError, ApiRequestError, type ApiClient } from '../../services/api'
import type { TicketNote } from '../../services/ticketWorkspaceSchemas'
import type { Ticket } from '../../types'
import { formatDate } from '../shared/presentationData'
import { isTerminal } from './ticketLifecycle'

type Props = { readonly ticket: Ticket; readonly client: ApiClient; readonly onRefresh: (id: string) => Promise<void>; readonly onSaved: () => void }
export function TicketNotes({ ticket, client, onRefresh, onSaved }: Props) {
  const [notes, setNotes] = useState<readonly TicketNote[]>([])
  const [content, setContent] = useState('')
  const [noteId, setNoteId] = useState(() => crypto.randomUUID())
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    if (ticket.version === undefined) { setLoading(false); return }
    setLoading(true)
    client.fetchTicketNotes(ticket.id, controller.signal).then((items) => {
      if (!controller.signal.aborted) { setNotes(items); setError(null) }
    }).catch((failure: unknown) => {
      if (controller.signal.aborted || (failure instanceof ApiRequestError && failure.kind === 'cancelled')) return
      setError(failure instanceof ApiError ? failure.message : '内部备注暂不可用')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [client, ticket.id, ticket.version, revision])
  const submit = async () => {
    if (!content.trim() || saving || ticket.version === undefined) return
    setSaving(true); setError(null)
    try {
      const note = await client.addTicketNote(ticket.id, content.trim(), ticket.version, noteId)
      setNotes((current) => [note, ...current.filter((item) => item.id !== note.id)])
      setContent(''); setNoteId(crypto.randomUUID()); onSaved()
      await onRefresh(ticket.id)
    } catch (failure: unknown) {
      if (failure instanceof ApiError && failure.code === 'VERSION_CONFLICT') await onRefresh(ticket.id)
      setError(failure instanceof ApiError ? failure.message : '保存未确认，请重试；重复提交不会新增相同备注。')
    } finally { setSaving(false) }
  }
  return <section className="section-block notes-section" aria-label="内部备注">
    <h3 className="section-label"><LockKeyhole size={14} /> 内部备注 <span className="section-count">{notes.length}</span></h3>
    <p className="field-hint">仅团队可见，不会发送给客户或自动提交给模型。</p>
    {error && <div className="inline-error" role="alert">{error}<button type="button" onClick={() => setRevision((value) => value + 1)}>重新加载</button></div>}
    {loading && <p role="status" className="field-hint">正在加载备注…</p>}
    {notes.map((note) => <article className="internal-note" key={note.id}><div><strong>{note.authorLabel}</strong><time>{formatDate(note.createdAt)}</time></div><p>{note.content}</p></article>)}
    {notes.length === 100 && <p className="field-hint">显示最近 100 条备注。</p>}
    {!isTerminal(ticket.status) && <div className="note-composer"><Input.TextArea aria-label="添加内部备注" value={content} onChange={(event) => { setContent(event.target.value); setNoteId(crypto.randomUUID()) }} rows={3} maxLength={4000} disabled={saving || ticket.version === undefined} placeholder={ticket.version === undefined ? '连接业务服务后添加内部备注' : '记录排查进展、交接事项或处理结论…'} />
      <div className="composer-footer"><span>{content.length} / 4000</span><Button size="small" icon={<Send size={13} />} loading={saving} disabled={!content.trim() || ticket.version === undefined} onClick={submit}>保存备注</Button></div>
    </div>}
  </section>
}
