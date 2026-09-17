# R2 Frontend Context Review

Reviewed: 2026-09-09

Scope: `TicketQueue`, `CommandPalette`, `TicketActivity`, `TicketDetail`,
`useTicketWorkflow`, `api.ts`, `ticketWorkspaceSchemas.ts`, `OverviewView`,
lazy-loading recovery, and their focused tests. Base HEAD was
`4df3bf44907c34318132496929bad4a3974ad88b`; the reviewed worktree is dirty.
This was a read-only review. I did not run tests; the final build-budget and
test evidence belongs to the executing agent.

## Verdict

**PASS for the reviewed frontend code.**

`codeQualityStatus`: **WATCH**

`recommendation`: **APPROVE**

`reportPath`: `.omo/evidence/r2-context-review.md`

`blockers`: None in the frozen frontend source. The current verification
document must finish being rewritten before it is used as current-run evidence.

## Findings

### CRITICAL

None.

### HIGH

None.

The final source closes the previously observed high-risk races:

- `useTicketWorkflow.ts:26-31` invalidates the queue epoch synchronously when
  the filter changes, and `:44-85` captures and verifies that epoch before
  applying a page. `:190-211` gives load-more the same protection.
- Successful ticket updates, assignment changes, analyses, creation, and review
  recording all invalidate the server page and metric snapshot. The resulting
  first page replaces `queueIds`, which corrects filtered membership and
  `X-Total-Count` without discarding a selected detail outside that filter.
- An analysis which was accepted by the command endpoint but whose detail read
  then fails is now distinguished at `:112-140`; the queue is invalidated
  before the detail read and the user is told that the analysis was saved.
- `App.tsx:78-86` wraps both the main view and command palette in recoverable
  lazy boundaries. Workbench and detail lazy components are created per mounted
  host component, so a boundary retry receives a fresh lazy cache.

### MEDIUM

1. **Current verification text was still in its first-round form at the time
   of this review.** [VERIFICATION.md](/Users/shika/Documents/Support-Copilot/docs/enterprise-workspace/VERIFICATION.md:5)
   describes its table as results for the *current* dirty worktree, but the
   frozen source has changed after those reported commands. Its limitation at
   [line 59](/Users/shika/Documents/Support-Copilot/docs/enterprise-workspace/VERIFICATION.md:59)
   also says SLA ordering and global search apply only to already-loaded data,
   which is no longer true. A historical copy,
   [VERIFICATION-R1.md](/Users/shika/Documents/Support-Copilot/docs/enterprise-workspace/VERIFICATION-R1.md:1),
   has correctly been introduced; the current file still needs replacement
   with final command output and the new behavior before it is relied on as
   evidence.

   [PILOT_OPERATIONS.md](/Users/shika/Documents/Support-Copilot/docs/PILOT_OPERATIONS.md:110)
   has already been corrected to document server-side filtering, cursor-bound
   sort/filter state, `X-Total-Count`, and global search. This finding is
   limited to finalizing the current verification artifact, not a product-code
   defect.

### LOW

None.

## Behavioral Evidence Reviewed

- A first page begins with the pending-status filter from
  [ticketWorkspaceSchemas.ts](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/services/ticketWorkspaceSchemas.ts:29).
  `fetchTicketPage` encodes keyword, status, priority, assignee, sort, cursor,
  and limit and reads both cursor/count headers in
  [api.ts](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/services/api.ts:178).
- The command palette sends an unscoped server keyword query, aborts the prior
  request on a new query, and accepts a response only while its controller is
  current in
  [CommandPalette.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/components/CommandPalette.tsx:19).
  `openTicket` merges an unloaded result into the ticket store before selecting
  it, so its detail can be opened without first loading a queue page.
- Activity history is keyed by ticket/version/analysis/review, aborts requests
  during a ticket change, preserves a successful first page when an older page
  fails, and deduplicates overlapping cursor boundaries in
  [TicketActivity.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/features/tickets/TicketActivity.tsx:16).
  A successfully saved note independently increments the activity key in
  [TicketDetail.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/features/tickets/TicketDetail.tsx:48),
  so a failed follow-up ticket read does not hide its durable activity entry.
- `TicketQueue` preserves server order for persisted tickets, reports the
  server's matching total, and applies client-side SLA/priority ordering only
  to versionless preview data in
  [TicketQueue.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/features/tickets/TicketQueue.tsx:39).
- The modular ECharts import and registration in
  [OverviewView.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/features/overview/OverviewView.tsx:2)
  match the two rendered chart types and provide accessible tabular equivalents.

## Test Relevance And Skill Perspectives

The `remove-ai-slops` and `programming` skill perspectives were loaded and
applied before judging tests and maintainability.

The focused tests are behavior-oriented rather than implementation-mirroring:

- [queueConsistency.test.ts](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/features/workbench/queueConsistency.test.ts:40)
  verifies that a resolved ticket disappears from the filtered queue while its
  selected detail remains, and at [line 83](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/features/workbench/queueConsistency.test.ts:83)
  resolves the old filtered page after changing the query.
- [CommandPalette.test.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/components/CommandPalette.test.tsx:18)
  covers selection of an item absent from the loaded page plus stale-query
  suppression and retry.
- [TicketActivity.test.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/features/tickets/TicketActivity.test.tsx:31)
  covers ticket switches, cursor failure/retry, durable-version reloads, and
  no fabricated legacy history.

I found no deletion-only, tautological, prompt-derived, or constant-mirroring
test added for this feature; no untyped escape hatch; and no unnecessary
production parsing/normalization beyond the Zod API boundary. The coordinating
workflow file is dense, but its state and effects remain within a single
ticket-workflow boundary and the added abstraction is limited to meaningful
queue invalidation and snapshot merging. The diff therefore does not
materially violate either skill perspective.

## Verification Limit

`git diff --check` was clean when inspected. No test command was executed by
this reviewer under the task constraint. The build/test claims must be read
from final executor-owned evidence after the verification document is updated.
