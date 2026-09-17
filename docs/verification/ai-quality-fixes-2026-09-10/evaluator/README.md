# Evaluator fixes — 2026-09-10

Implemented and verified locally. No external model or Embedding calls were made by this subtask. Evidence is from the dirty shared workspace, based on Git `4df3bf44907c34318132496929bad4a3974ad88b`; it is not a clean-commit release attestation.

## Behavior

- `LiveTicket.language` defaults to `zh-CN` for existing datasets and is explicitly forwarded to `TicketInput`.
- Optional per-case `expected_language` accepts `zh` or `en`. Results record `language_correct`; this is a deliberately coarse script heuristic: English requires Latin letters and no CJK ideographs; Chinese requires CJK ideographs. It is not language fluency, translation accuracy, or factual support verification.
- Optional per-case `forbidden_reply_patterns` is a tuple of up to 16 bounded regexes. The result retains exact matched source patterns in `policy_violations`. This detects enumerated regression phrases; it cannot infer all business-policy semantics.
- Patterns are compiled and validated at the dataset boundary: 1–512 characters, no groups/lookarounds/backreferences/unbounded quantifiers, at most two bounded quantifiers, upper bounds at most 64, and no empty match. Text beyond 16,000 characters fails the check rather than being silently truncated.
- Results preserve `reply_warnings`. The machine gate rejects failed language checks and any policy violations. The report verifier recomputes these checks from original response text and dataset expectations, rejecting forged result fields.
- New summaries use nearest-rank p95 (`ceil(n * 0.95) - 1` as the zero-based sample index). For 16 samples the p95 is the maximum sample. Schema-v1 summaries without `p95_method` retain `legacy-rounded-index` interpretation during verification and human-review application. Old results are not silently rewritten.
- `run.runtime_source_sha256` hashes relative paths and contents of `app/**/*.py` and `app/**/*.json`, including prompts, schemas and response policies. This is also bound into the configuration fingerprint, so an unchanged Git SHA and dirty flag cannot hide a changed runtime. Historical reports default the field to null; they will not match newly captured runtime provenance.
- A terminal live/fallback response is required; a mock or RUNNING result cannot be relabeled as a live evaluation result.
- For `insufficient_evidence`, observed live candidates retain IDs, scores and rankings for diagnosis but all have `used_as_evidence=false`. Final response retrieval and citation evidence remain separately recorded.

## Evidence

All final commands below ran from `services/support-copilot-ai`.

- Red: `red.log` contains 10 failures / 3 passes before fields/gates/p95 implementation.
- Provenance red: `provenance-red.log` contains 2 failures / 13 passes before runtime-source binding.
- Policy-data provenance red: `policy-provenance-red.log` proves a JSON-only policy edit was previously invisible.
- Rejected-candidate observation red: `observation-red.log` proves unused live candidates were previously marked as evidence.
- Green: `.venv/bin/python -m pytest tests/test_live_accepted_evidence.py tests/test_live_quality_checks.py tests/test_live_evaluation.py tests/test_live_evaluation_gates.py tests/test_live_provenance.py tests/test_live_outcome_capture.py tests/test_live_retrieval_observation.py -q` → **88 passed** (`green.log`), including **27 new cases**.
- `uv tool run ruff check evaluation/live_models.py evaluation/live_runner.py evaluation/live_reply_checks.py evaluation/live_summary.py evaluation/live_verifier.py evaluation/live_provenance.py evaluation/live_review.py evaluation/live_markdown.py tests/test_live_quality_checks.py` → pass (`ruff.log`).
- The same eight production files with `uv tool run basedpyright --pythonpath .venv/bin/python` → **0 errors / 0 warnings** (`production-types.log`). Including the new test module gives 0 errors / 4 warnings for intentional reuse of existing private test fixtures and the private result-capture seam (`types.log`). No diagnostic was suppressed.
- `git diff --check` on evaluator files and the new test module passed.

No human factual-support reviews were filled. Machine checks remain independent from the human release gate. Full runtime regression and real-model reruns are owned by the parent task.

## Follow-up: retained API candidates

The API may retain rejected candidates with `used_as_evidence=false`. Evaluator `retrieved_chunk_ids`, `retrieval_methods`, citation-label resolution and `response_evidence` use only final adopted hits (`used_as_evidence=true`). `live_retrieval` remains the raw vector candidate observation for Recall/ranking diagnosis. With no adopted/cited evidence the response-evidence list is empty. Original reply citation labels are retained so references to rejected candidates cannot disappear silently.

`accepted-evidence-red.log` contains three failing cases before this fix. `green.log` now records 88 passing tests including the retained-candidate success and two failure paths: `invalid_model_response` and `structured_generation_response_timeout` remain machine-gate failures even when their final adopted evidence is empty. The changed runner passes basedpyright with 0 errors / 0 warnings (`accepted-evidence-types.log`); Ruff passes (`accepted-evidence-ruff.log`).
