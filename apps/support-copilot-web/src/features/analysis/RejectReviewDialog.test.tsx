// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useRef, useState } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { RejectReviewDialog } from './RejectReviewDialog'

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => vi.stubGlobal('ResizeObserver', TestResizeObserver))
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function DialogOwner() {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  return <div data-testid="dialog-owner" data-dialog-open={open}>
    <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>open rejection</button>
    <RejectReviewDialog open={open} confirming={false} errorMessage={null} returnFocusRef={triggerRef} onCancel={() => setOpen(false)} onConfirm={vi.fn()} />
  </div>
}

it('wraps focus forward and backward while open', async () => {
  // Given: the rendered rejection dialog is open with enabled edge controls.
  render(<DialogOwner />)
  fireEvent.click(screen.getByRole('button', { name: 'open rejection' }))
  fireEvent.change(await screen.findByLabelText('拒绝原因'), { target: { value: '证据不足' } })
  const dialog = screen.getByRole('dialog', { name: '拒绝回复建议' })
  const controls = [...dialog.querySelectorAll<HTMLElement>('button:not([disabled]), textarea:not([disabled])')]
  const first = controls[0]
  const last = controls.at(-1)
  expect(first).toBeDefined()
  expect(last).toBeDefined()

  // When: Tab leaves the last control and Shift+Tab leaves the first control.
  last?.focus()
  fireEvent.keyDown(last ?? dialog, { key: 'Tab' })
  expect(document.activeElement).toBe(first)
  first?.focus()
  fireEvent.keyDown(first ?? dialog, { key: 'Tab', shiftKey: true })

  // Then: focus wraps to the opposite edge in both directions.
  expect(document.activeElement).toBe(last)
})

it('restores trigger focus after Escape', async () => {
  // Given: the trigger opened the rendered rejection dialog.
  render(<DialogOwner />)
  const trigger = screen.getByRole('button', { name: 'open rejection' })
  fireEvent.click(trigger)
  const reason = await screen.findByLabelText('拒绝原因')

  // When: Escape closes the dialog.
  reason.focus()
  fireEvent.keyDown(reason, { key: 'Escape' })

  // Then: the owner closes and focus returns to its trigger.
  await waitFor(() => expect(screen.getByTestId('dialog-owner').getAttribute('data-dialog-open')).toBe('false'))
  await waitFor(() => expect(document.activeElement).toBe(trigger))
})

it('does not trap focus while closed', () => {
  // Given: the dialog has never been opened.
  render(<DialogOwner />)
  const trigger = screen.getByRole('button', { name: 'open rejection' })
  trigger.focus()

  // When: a Tab keydown occurs outside the closed dialog.
  const allowed = fireEvent.keyDown(trigger, { key: 'Tab' })

  // Then: no closed-dialog handler cancels the keyboard event.
  expect(allowed).toBe(true)
})
