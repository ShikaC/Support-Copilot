# Enterprise workspace rebuild

User authorization: 2026-09-09 direct implementation, superseding previous teaching/pause restrictions. Existing uncommitted infrastructure edits are preserved.

1. Make ticket management usable end to end: creation form, cursor-aware queue loading/search, assignment and priority/category edit, explicit legal lifecycle actions, internal notes with actor/time, visible request failures. Keep server authoritative and version checks intact.
2. Refactor the workspace into clear queue/customer/assistant surfaces, token-based responsive design, accessible navigation and command search. Retain working knowledge, audit and quality features.
3. Improve workflow reliability: operation-specific timeout, preserve prior analysis on failed reanalysis, refresh metrics after metric-affecting writes (create, property/status/assignment updates and review), avoid mistaken demo success for persisted commands.
4. Verify full frontend regression/build budget, focused + full Java regression, Python regression, browser normal/failure/mobile flows and real Java/Python mock integration. Record evidence and limitations; keep local changes reviewable.

Data path: browser validated command → Java domain/version checks → transaction + audit → authoritative ticket → browser queue/detail/metrics. Analysis: Java → authenticated Python workflow → evidence/structured result → Java version check/persistence → human review. Notes are internal business data, never automatically sent to AI or customers.
