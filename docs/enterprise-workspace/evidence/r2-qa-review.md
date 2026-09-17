# R2 Boundary QA Review

Date: 2026-09-09
Surface: `http://127.0.0.1:18173/`
Mode: localhost demo API, synthetic QA ticket permitted by assignment
Observed SHA: `4df3bf44907c34318132496929bad4a3974ad88b`
Worktree: already dirty before QA; no product code edited by this review.

Synthetic data used: created `ticket-27fe3813-2187-47c0-8635-cff56f54d048` (`SC-78E7E3E92DE34B928070BCDA0DB18`) with subject `QA activity pagination 2026-09-09`, then applied five updates to generate activity pages. A second synthetic ticket `ticket-571727bc-43e2-43e2-bb45-2bd0d2c160e3` (`SC-0C91F89CDF9D425882E00A6016264`) was transitioned through `IN_PROGRESS -> RESOLVED -> CLOSED` for terminal-state protection checks.

## Scenario Matrix

| ID | Scenario / exact invocation | Expected | Verdict | Evidence |
|---|---|---|---|---|
| R2-01 | `GET /api/tickets?limit=20&sort=NEWEST` | Results descend by `createdAt` | PASS | `sort-assignee-api.json` |
| R2-02 | `GET /api/tickets?limit=20&sort=SLA` | Results ascend by `slaDeadline` | PASS | `sort-assignee-api.json` |
| R2-03 | `GET /api/tickets?limit=20&sort=PRIORITY` | URGENT, HIGH, MEDIUM, LOW order | PASS | `sort-assignee-api.json` |
| R2-04 | UI queue sort select: `最新创建`, `SLA 最紧急`, `优先级最高` | First-row order agrees with API | PASS | `sort-assignee.json` |
| R2-05 | `GET /api/tickets?limit=20&assignee=UNASSIGNED` | Only unassigned tickets; total matches items | PASS | `sort-assignee-api.json` |
| R2-06 | `GET /api/tickets?limit=20&assignee=%E5%91%A8%E5%B2%9A` | Exact assignee match; total 1 | PASS | `sort-assignee-api.json` |
| R2-07 | UI assignee select `未分配负责人` | Four visible rows | PASS | `sort-assignee.json` |
| R2-08 | UI assignee select `指定负责人`, input `周岚` | One queue result, SC-10042 | PASS | `sort-assignee.json`, `sort-assignee-api.json` |
| R2-09 | Open command palette, input `SC-10018`, click matching result | Detail opens for non-initial ticket SC-10018 | PASS | `shortcut.json` |
| R2-10 | `GET /api/tickets/{synthetic}/activity?limit=2`, then repeat with returned `cursor` | Distinct pages, valid next cursor | PASS | `activity-pagination.json` |
| R2-11 | `GET /api/tickets/{synthetic}/activity?limit=2&cursor=bad-cursor-xyz` | Structured 400 `INVALID_TICKET_CURSOR` | PASS | `activity-pagination.json` |
| R2-12 | Browser route aborts first activity request after selecting SC-10041; click `重新加载处理记录` | Error is visible, retry clears error and loads activity | PASS | `activity-retry.json` |
| R2-13 | `PATCH` synthetic status `IN_PROGRESS`, then `RESOLVED`, then `CLOSED` with expected versions | Valid terminal transition succeeds | PASS | `terminal-protection.txt` |
| R2-14 | `POST /api/tickets/{synthetic}/claim` at CLOSED, version 3 | 409 `TICKET_STATE_CONFLICT` | PASS | `terminal-protection.txt` |
| R2-15 | `POST /api/tickets/{synthetic}/unassign` at CLOSED, version 3 | 409 `TICKET_STATE_CONFLICT` | PASS | `terminal-protection.txt` |
| R2-16 | `POST /api/tickets/{synthetic}/analyze` with idempotency key at CLOSED | 409 `TICKET_STATE_CONFLICT` | PASS | `terminal-protection.txt` |

## Findings

No functional defect was reproduced in the requested new boundaries.

The initial UI assignee-count probe used a page-wide `SC-10042` text locator and saw two matches because the selected detail panel repeats the queue ticket number. The scoped queue row count was one, and the direct API response had `X-Total-Count: 1`; this is a QA locator ambiguity, not a product defect.

The first synthetic create-and-patch Node probe did not emit output because the long-lived local API call exceeded the command window, but the create succeeded and the remaining updates were rerun individually with bounded `curl --max-time 8` invocations. The final evidence uses only those completed requests.

## Artifact References

| ID | Kind | Description | Path |
|---|---|---|---|
| `sort-assignee-api` | JSON | Direct API sort and assignee responses, totals, and ordered rows | `/tmp/support-review-r2/sort-assignee-api.json` |
| `sort-assignee` | JSON | Browser UI sort and assignee observations | `/tmp/support-review-r2/sort-assignee.json` |
| `shortcut` | JSON | Command palette search and opening SC-10018 | `/tmp/support-review-r2/shortcut.json` |
| `activity-pagination` | JSON | Activity first page, cursor page, and invalid cursor response | `/tmp/support-review-r2/activity-pagination.json` |
| `activity-retry` | JSON | Browser network-abort failure and successful retry | `/tmp/support-review-r2/activity-retry.json` |
| `terminal-protection` | transcript | Closed transition, claim/unassign/analyze terminal responses | `/tmp/support-review-r2/terminal-protection.txt` |
