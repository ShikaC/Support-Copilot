# R2 Secondary Visual QA: PASS

## Scope and Evidence

This is a read-only secondary review of the current R2 workspace only. It does
not rely on superseded R1 screenshots or findings.

- **Rendered surface:** five routes (`工单工作台`, `运营概览`, `知识库`,
  `审计记录`, `质量评估`) at `1600`, `1280`, `768`, and `375` widths.
- **Primary artifacts:** the 20 screenshots under
  [`docs/enterprise-workspace/screenshots`](../screenshots),
  including [`workbench-375.png`](../screenshots/workbench-375.png),
  [`workbench-768.png`](../screenshots/workbench-768.png),
  [`audit-375.png`](../screenshots/audit-375.png),
  [`overview-375.png`](../screenshots/overview-375.png), and
  [`quality-375.png`](../screenshots/quality-375.png).
- **Automation evidence:** [`surface-results.json`](../screenshots/surface-results.json)
  records all 20 surface/viewport pairs with `overflow: 0`, no axe violations,
  and no page errors. [`workflow-results.json`](../screenshots/workflow-results.json)
  records the real local Java plus deterministic Python mock workflow with no
  browser errors.
- **Freshness and validity:** the reviewed screenshots are RGB PNGs at their
  requested widths and were written at `2026-09-09 16:31-16:32`, after the
  relevant R2 frontend source changes (the reviewed `App.tsx` was modified at
  `16:10`; queue and CSS earlier). No black/compositor-missing regions were
  observed.
- **Independent inputs:** I inspected the source and captures directly. A
  focused secondary CJK pass separately found no product defect; it noted that
  the detail-state 375px screenshot does not itself show queue controls. The
  existing final visual reviewer inspected the complete 20-capture set and
  returned PASS. This report preserves the capture limitation below rather than
  treating it as unverified product failure.

## Result

| Dimension | Verdict | Evidence |
| --- | --- | --- |
| Live UI rather than screenshot reconstruction | PASS | React/Ant Design component tree and real handlers in `App.tsx`, `WorkbenchView.tsx`, `TicketQueue.tsx`, and route views; workflow evidence exercises persisted commands. |
| Desktop workbench hierarchy | PASS | `workbench-1600.png` and `workbench-1280.png` show a usable queue, detail, and assistant composition with settled analysis/closed states. |
| 768px queue controls | PASS | `workbench-768.png` shows search, status scope, priority, server sort, and assignee controls with readable labels and no overlap; each is a labelled interactive control in [`TicketQueue.tsx:59`](../../../apps/support-copilot-web/src/features/tickets/TicketQueue.tsx). |
| 375px operator workflow | PASS | `workbench-375.png` shows the intended detail-first mobile flow and real return button. The state transition is implemented in [`WorkbenchView.tsx:34`](../../../apps/support-copilot-web/src/features/workbench/WorkbenchView.tsx); the completed 21-case browser suite covers the mobile interaction path. |
| CJK and long identifiers | PASS | `audit-375.png` uses labelled vertical records; long target IDs wrap rather than crop under [`workspace.css:147`](../../../apps/support-copilot-web/src/workspace.css). Activity metadata uses `overflow-wrap:anywhere` at [`workspace.css:159`](../../../apps/support-copilot-web/src/workspace.css). Workflow trace/prompt values and 375px knowledge/quality copy remain readable in their captures. |
| Mobile table information | PASS | The current 375px audit/quality captures use stacked record layouts and retain actor, trace, evaluation metrics, and gate fields rather than hiding right-side columns. |
| Responsive charts and non-workbench routes | PASS | Current overview captures show settled trend/category charts. Knowledge, audit, and quality captures contain ready-state content, not loading placeholders; quality visibly labels the mock/offline evaluation context. |
| Accessibility and overflow | PASS | `surface-results.json`: 20/20 pairs have zero document overflow, zero axe violations, and zero page errors. |

## Capture Caveat

`workbench-375.png` is intentionally in the selected-ticket detail state, which
hides the queue. It cannot by itself visually demonstrate the queue controls at
375px. This is an evidence granularity limitation, not a rendered defect: the
768px screenshot demonstrates the same control group, the mobile back button is
real and covered by the browser suite, and the 375px CSS gives the two filter
controls equal responsive tracks. A future screenshot refresh can add the
post-back queue state, but no source change or matrix rerun is required for the
current R2 verdict.

## Skill Check

The `omo:visual-qa` skill was loaded and applied. It guided screenshot validity,
freshness, responsive, CJK, interaction, and evidence-boundary checks. The UI is
real DOM rather than a raster substitute. No current-source visual blocker, CJK
clipping issue, contrast failure, or operability defect was found in this pass.

```text
visualStatus: PASS
recommendation: APPROVE
reportPath: .omo/evidence/r2-visual-secondary.md
blockers: []
```
