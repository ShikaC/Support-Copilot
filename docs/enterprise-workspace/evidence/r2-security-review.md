# R2 Security Review: Queue, Activity, V7, and Workspace Persistence

## Result

**PASS.** All P1 and P2 conditions in this R2 review are closed in the current
worktree. The anonymous `demo` profile is now constrained by an application
startup whitelist as well as by the workspace launcher.

## Review Basis

- **Current commit:** `4df3bf44907c34318132496929bad4a3974ad88b`.
- **Worktree:** dirty, with reviewed R2 additions untracked. This review applies
  to the current worktree rather than to that commit.
- **Reviewed code:** `TicketQueue*`, `ticket/activity/*`, note/audit integration
  points, V6/V7, workspace launcher and recovery scripts, profile/security
  configuration, and focused tests.
- **Execution boundary:** this was read-only. I did not start or stop the
  workspace, run Gradle, run MySQL/Testcontainers, or call external APIs.
- **Lock evidence:** the current SHA-256 values of `workspace-data.sh`,
  `workspace_data.py`, and both recovery test scripts match
  [`workspace-lock-results.json`:13](../../../.omo/evidence/workspace-lock-results.json).
  That artifact records H2 2.4.240 bidirectional file-lock interoperability and
  three deterministic cases covering backup and replacement race windows. I
  verified the current helper's locking protocol but did not re-run it.
- **Persistence evidence:**
  [`persistence-results.json`:41](../persistence-results.json)
  records an offline backup/restore preserving 12 ticket IDs/versions and note
  fields. It names the pre-rename `application-workspace.properties`; the
  current `workspace-defaults.properties` has the same recorded SHA-256 content
  (`6a0cb72...eb10`), while the launcher now passes the renamed classpath file.
  Therefore this is valid historical recovery evidence for the unchanged H2
  settings, not a claim that the renamed launcher was re-run in this review.
- **Listener test evidence:** the current JUnit XML records 24
  `RuntimeProfileIntegrationTests`, with zero skips, failures, or errors. The
  supplied Gradle log also reports a successful run. I inspected these artifacts
  but did not execute Gradle myself.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Closure Verification

### P1: Activity projection redacts authenticated audit subjects

`TicketActivityService` maps `AUTHENTICATED_JWT` to the controlled string
`"已认证操作人"`, without reading `event.getActorSubject()` while projecting the
agent-visible response
([`TicketActivityService.java:66`](../../../services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/activity/TicketActivityService.java)).
The focused API test makes a request authorized only as `SUPPORT_AGENT`, asserts
that fixed actor label, and asserts known actor subjects, metadata fields,
sensitive canaries, and a different ticket ID are absent
([`TicketActivityApiTests.java:83`](../../../services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/ticket/activity/TicketActivityApiTests.java)).

### P1: Recovery operations keep OS locks through copy and replacement

The shell entry point validates workspace paths and the manifest before
delegating the file operation to the helper
([`workspace-data.sh:41`](../../../scripts/workspace-data.sh)).
`database_lock` opens the database with `O_NOFOLLOW`, verifies a regular file,
acquires an exclusive non-blocking POSIX lock, and confirms the pathname still
names that locked inode
([`workspace_data.py:32`](../../../scripts/workspace_data.py)).
Backup copies from that descriptor. Restore retains the old-inode lock, locks the
temporary replacement inode before copy, fsyncs and verifies its digest, then
renames while both descriptors remain open
([`workspace_data.py:109`](../../../scripts/workspace_data.py)).

The Python test uses independent processes to attempt a lock during backup copy,
restore copy, immediately before replacement, and immediately after replacement
([`test_workspace_data.py:55`](../../../scripts/tests/test_workspace_data.py)).
The hash-bound evidence additionally records a real H2 interoperability probe
and persisted-workspace restore readback.

### P2: Application startup now enforces demo loopback addresses

`application-demo.properties` provides `server.address=127.0.0.1`
([`application-demo.properties:1`](../../../services/support-copilot-api/src/main/resources/application-demo.properties)).
The globally registered application initializer reads the effective address while
the Spring context is prepared and allows only explicit loopback forms for
`demo`; blank, wildcard, external, and arbitrary-domain values fail before
context refresh
([`RuntimeProfileApplicationContextInitializer.java:24`](../../../services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/config/RuntimeProfileApplicationContextInitializer.java)).
The workspace launcher remains explicitly loopback-bound and passes
`workspace-defaults.properties` as its durable H2 configuration
([`dev-workspace.sh:42`](../../../scripts/dev-workspace.sh)).

`RuntimeProfileIntegrationTests` uses a real `SpringApplicationBuilder`, not a
mock-only property check, to cover the default, accepted IPv4/IPv6 loopback
forms, rejected `0.0.0.0`, `::`, external IP, domain, and blank values, plus the
unchanged pilot/test policy
([`RuntimeProfileIntegrationTests.java:75`](../../../services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/config/RuntimeProfileIntegrationTests.java)).
The test XML reports all 24 parameterized cases green.

## Other Confirmed Controls

- Queue filters parse into bounded, allowlisted domain values. Criteria API
  predicates bind values, escape LIKE metacharacters, and bind the canonical
  filter/sort fingerprint into the cursor.
- Activity cursors carry the ticket ID and reject cross-ticket reuse before
  querying. The repository uses bound values and associates analysis/review
  audit events with the requested ticket.
- Activity detail is a controlled summary: it does not project note content,
  reply/rejection text, audit metadata, role arrays, or raw actor subjects.
- Note writes lock the ticket before checking the ticket-scoped request ID,
  enforce expected version, and record the trusted actor audit event in the same
  transaction ([`TicketNoteService.java:33`](../../../services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketNoteService.java)).
  V6 enforces `(ticket_id, request_id)` uniqueness
  ([`V6__ticket_internal_notes.sql:1`](../../../services/support-copilot-api/src/main/resources/db/migration/V6__ticket_internal_notes.sql)).
- V7 is fixed DDL only and matches the static JPA mappings. No user input is
  concatenated into schema or business queries.

## Test and Skill Perspective

The `omo:programming` and `omo:remove-ai-slops` perspectives were loaded and
applied in this session. The programming pass found no untyped escape hatch,
unsafe query construction, or needless parsing at the changed boundaries. The
remove-ai-slops pass found no deletion-only, tautological, prompt/prose, or
implementation-mirroring test, and no unnecessary production data extraction.
The actor canaries, independent-process lock probes, and real Spring startup
cases exercise behavior that would regress if the corrections were removed. The
current diff does not violate either skill perspective.

## Decision

```text
securityStatus: PASS
codeQualityStatus: CLEAR
recommendation: APPROVE
reportPath: .omo/evidence/r2-security-review.md
blockers: none
```
