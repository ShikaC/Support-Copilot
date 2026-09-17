# Live evaluation integrity: final integration review

2026-09-09. Result: no new runtime correctness blocker found in the reviewed integration. The machine gate remains separate from real human factual-support approval. The final baseline itself must be interpreted using all captured runs, not only successful examples.

This is an automated engineering review, not a human factual-support review of model replies. No reviewer slots were filled. No external API calls were made by this reviewer. Runtime source was left unchanged during the frozen final runs.

## Scope and verified changes

- `evaluation/live_summary.py`: a safe expected no-evidence result must have FALLBACK status, fallback mode, insufficient_evidence reason, empty retrieved/cited evidence, and a true captured escalation decision. Wrong classification/escalation outcomes fail the machine gate. Completed PARTIAL/UNSUPPORTED human judgments cannot make a report publishable; whitespace-only reviewer metadata is incomplete.
- `evaluation/run_live_evaluation.py`: exit code follows the machine gate, so an intended no-evidence fallback is accepted without pretending human approval exists.
- `evaluation/live_verifier.py`: real dataset context binds exact case IDs/count, allowed chunks, retrieval outcome/rank, citation consistency and classification/escalation judgments. Fabricated report success flags and missing/duplicated cases are rejected. Legacy contexts without expected cases retain compatibility.
- `evaluation/live_models.py` and `evaluation/live_runner.py`: actual classification, escalation decision, trace ID, original citation labels and retrieval method are retained; expectations are evaluated against actual returned values.
- `evaluation/live_observation.py`: the actual live retrieval is retained separately from later local fallback retrieval, including the distinction between an observed empty result and an unobserved result. Per-ticket observations are consumed after each sequential evaluation case.
- `app/models.py` and `app/openai_provider.py`: both supported provider protocols request the existing enterprise category vocabulary through StructuredModelDraft. Unexpected provider labels fail structured validation before reaching risk decisions. The existing BILLING/PRIVACY/SECURITY/LEGAL escalation policy consequently receives known category names. This prevents unknown labels from bypassing the policy; it does not by itself guarantee correct classification.

## Commands and evidence

Commands run from `services/support-copilot-ai` unless shown otherwise. Git HEAD was `4df3bf44907c34318132496929bad4a3974ad88b`; the shared working tree was dirty (144 status entries at final review). These are current working-tree checks, not proof that the clean HEAD contains the changes. Exact source identity belongs to the baseline source manifest.

| Stage | Command / result | Archived evidence |
|---|---|---|
| Initial red | `.venv/bin/python -m pytest tests/test_live_evaluation_gates.py -q`: 11 failed, 1 passed | `support-live-gates-red.log` |
| Dataset binding red | Same focused module after adding binding regressions: 8 failed, 14 passed | `support-live-gates-red-binding.log` |
| Additional red cases | No-evidence live response bypass; unresolved citation label bypass | `support-live-gates-red-live-no-evidence.log`, `support-live-gates-red-label.log` |
| Evaluator green | `.venv/bin/python -m pytest tests/test_live_evaluation_gates.py tests/test_live_evaluation.py tests/test_live_provenance.py -q`: 59 passed | `support-live-gates-green.log` |
| Final integration | Above three modules plus `tests/test_live_category_contract.py tests/test_live_outcome_capture.py tests/test_live_retrieval_observation.py tests/test_openai_provider_protocols.py tests/test_openai_chat_protocol_errors.py`: 76 passed | `support-live-gates-final-integration.log` |
| Production typing | `uv tool run --offline basedpyright --pythonpath .venv/bin/python evaluation/live_summary.py evaluation/run_live_evaluation.py evaluation/live_verifier.py`: 0 errors, 0 warnings | `support-live-gates-final-types.log` |
| Final lint | From repository root, `uv tool run --offline ruff check` against the four initially owned files: one I001 import-order finding in the frozen runner; no auto-fix performed | `support-live-gates-lint.log` |

The earlier production typing log is also preserved. The earlier broad typing attempt from the repository root produced import-resolution errors; the subsequent service-root check resolved those. The initial all-four-files type check also includes two expected private-test-fixture usage warnings. These intermediate logs are historical diagnostics, not final production typing failures.

## Remaining limitations and interpretation

1. The frozen runner has a nonblocking import-order lint finding at `evaluation/run_live_evaluation.py:15`, introduced with ObservedKnowledgeRetriever. Preserve frozen source attribution before any later formatting change.
2. `summary.retrieval_success` describes evidence in the returned response; on provider failure that response can contain local fallback evidence. Use `live_retrieval` for vector-only analysis. Correct no-evidence withholding is a safety success, not a positive knowledge retrieval hit.
3. `live_summary.py` currently uses the rounded-index quantile `sorted[round((n-1)*0.95)]`. This is not the nearest-rank definition `ceil(0.95*n)-1`. At 16 cases it selects the 15th latency; final-1 reports 10089 ms although its maximum is 10590 ms. A baseline aggregate should identify the method or independently report nearest-rank p95. No frozen runtime changes were made for this historical calculation.
4. Machine citation checks establish allowed/retrieved ID consistency, not that every sentence is factually supported. ResponseEvidence currently maps the entire reply to evidence indexes. Real human review remains required and NOT_REVIEWED slots must remain untouched by automated reviewers.
5. Live retrieval observation is diagnostic evidence. The existing report verifier does not independently re-run remote retrieval or authenticate provider-internal routing, reported usage, latency or cost. Unknown prices remain unavailable rather than zero.
6. Classification/escalation fields are optional for old reports. The new actual runner populates them and the real VerificationContext binds the dataset expectations. Legacy report compatibility must not be presented as equivalent measurement coverage.
7. Fixed small synthetic data, two runs and successful machine gates do not establish production generalization, representative customer accuracy, concurrency SLOs or long-term stability. Retain the failed diagnostic runs and distinguish schema/source revisions.

At review time, final-1 reports 16 machine-passing cases, 13 live successes and three expected no-evidence fallbacks, with 0/16 human reviews and publishable=false. The run correctly avoids equating a passing machine gate with a publishable quality conclusion. Root owns final-2 and the consolidated baseline conclusions.

## Subsequent automated semantic spot check

Both final reports were subsequently read against the cited bundled corpus. The findings below are AI review concerns for the human worksheet; no human fields or raw reports were changed. The earlier engineering result does not imply that all replies satisfy policy.

- **Definite policy conflict — final-1 / quality-billing-injection.** `final-1/live-latest.json:1168` quotes a conditional 3–7 working day refund timeframe while the ticket still requires transaction verification. The cited `chunk-refund-02` (`app/data/knowledge.json:39`) explicitly prohibits citing that timeframe before verification. Saying "if approved" does not satisfy that prerequisite. final-2 of the same case omits the timeframe and aligns with this boundary. The two final runs therefore must not be described as 32/32 reply-policy-safe solely because machine gates pass.
- **Human review needed — final-1 / quality-sync.** `final-1/live-latest.json:1054` adds whether the error can be reproduced on a network without the company proxy. The cited `chunk-sync-2047` (`app/data/knowledge.json:137`) supports recording client/system versions and proxy configuration, but does not supply this additional diagnostic step. This is an unsupported extension requiring review, not evidence of a proven harmful instruction. final-2 stays closer to the cited recording requirements.
- **Usability concern — both runs / quality-sso-english.** The English request receives a Chinese reply. The dataset does not currently assert response-language matching, so this is not a failed machine expectation. It should nevertheless be assessed by the human reviewer if English-language customer use is intended.

The remaining sampled replies preserve the main source prerequisites: identity before administrator unlock, approval before invoice reissue, authorization/compliance review before employee-data operations, and no invented fixed seat price. The standalone quality-refund case explicitly states that approval has already happened, so its 3–7 working day wording does not have the injection case's prerequisite conflict. Duplicate-charge actual priorities are HIGH and escalation is true in both final runs.

Root reported a subsequent import-order cleanup and an equivalent str-plus-enum-schema category validator, with exact generated-schema equality and repeated rejection tests. Those later source changes belong to the additional final source manifest; they are not retroactively attributed to the frozen final-1/final-2 runtime.
