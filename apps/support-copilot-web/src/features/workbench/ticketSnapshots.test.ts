import { expect, it } from 'vitest'
import { ticketResponsePayload } from '../../test/apiFixtures'
import { mergeTicketSnapshots } from './useTicketWorkflow'

it('keeps a completed command when an older queue refresh arrives late', () => {
  const current = { ...ticketResponsePayload, events: [], version: 4, assigneeName: '已确认负责人' }
  const stale = { ...ticketResponsePayload, events: [], version: 3, assigneeName: null }
  expect(mergeTicketSnapshots([current], [stale])).toEqual([current])
})
it('reconciles newer snapshots and keeps selected tickets outside a filtered page', () => {
  const selected = { ...ticketResponsePayload, events: [], id: 'selected', version: 2 }
  const newest = { ...ticketResponsePayload, events: [], version: 4 }
  expect(mergeTicketSnapshots([selected, { ...ticketResponsePayload, events: [], version: 3 }], [newest])).toEqual([newest, selected])
})
