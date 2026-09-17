import json
import re
from math import isfinite
from typing import Final

from evaluation.citation_validation import citation_ids_are_valid
from evaluation.live_models import (
    LiveCaseResult,
    LiveEvaluationCase,
    LiveEvaluationReport,
    VerificationContext,
)
from evaluation.live_reply_checks import language_correct, policy_violations
from evaluation.live_summary import review_is_complete, summarize_live_cases

SENSITIVE_PATTERNS: Final = (
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"(?i)(api[_-]?key|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
)


def verify_live_report(
    report: LiveEvaluationReport,
    context: VerificationContext,
    *,
    require_human: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    run = report.run
    provenance = report.provenance
    if (run.dataset_id, run.dataset_version, run.dataset_checksum) != (
        context.dataset_id, context.dataset_version, context.dataset_checksum
    ):
        reasons.append("dataset-provenance-mismatch")
    if (provenance.knowledge_release_id, provenance.knowledge_release_version) != (
        context.release_id, context.release_version
    ):
        reasons.append("knowledge-release-mismatch")
    if provenance.semantic_corpus_checksum != context.corpus_checksum:
        reasons.append("semantic-corpus-mismatch")
    artifact = provenance.embedding_artifact
    if artifact is None or (artifact.artifact_id, artifact.manifest_sha256) != (
        context.artifact_id, context.artifact_manifest_sha256
    ):
        reasons.append("embedding-artifact-mismatch")
    if run.git_commit != context.git_commit:
        reasons.append("git-commit-mismatch")
    if run.worktree_dirty != context.worktree_dirty:
        reasons.append("git-dirty-state-mismatch")
    expected = context.configuration
    if run.prompt_version != expected.prompt_version:
        reasons.append("prompt-version-mismatch")
    if run.top_n != expected.top_n:
        reasons.append("top-n-mismatch")
    if run.top_k != expected.top_k:
        reasons.append("top-k-mismatch")
    if run.runtime_source_sha256 != expected.runtime_source_sha256:
        reasons.append("runtime-source-mismatch")
    if run.config_fingerprint != expected.config_fingerprint:
        reasons.append("config-fingerprint-mismatch")
    if provenance.chat_provider_identity != expected.chat_provider_identity:
        reasons.append("chat-provider-identity-mismatch")
    if provenance.chat_model != expected.chat_model:
        reasons.append("chat-model-mismatch")
    if provenance.chat_protocol != expected.chat_protocol:
        reasons.append("chat-protocol-mismatch")
    if artifact is not None:
        if artifact.provider_identity != expected.embedding_provider_identity:
            reasons.append("embedding-provider-identity-mismatch")
        if artifact.model != expected.embedding_model:
            reasons.append("embedding-model-mismatch")
        if artifact.dimension != expected.embedding_dimension:
            reasons.append("embedding-dimension-mismatch")
        if artifact.chunking_version != expected.embedding_chunking_version:
            reasons.append("embedding-chunking-version-mismatch")
    if report.summary != summarize_live_cases(report.cases, p95_method=report.summary.p95_method):
        reasons.append("summary-mismatch")
    expected_cases = {case.id: case for case in context.expected_cases}
    if expected_cases and (
        len(report.cases) != len(expected_cases)
        or {case.case_id for case in report.cases} != set(expected_cases)
    ):
        reasons.append("dataset-case-ids-mismatch")
    for case in report.cases:
        expected_case = expected_cases.get(case.case_id)
        if expected_case is not None:
            reasons.extend(_verify_case_expectations(case, expected_case))
        retrieved = set(case.retrieved_chunk_ids)
        allowed = set(case.allowed_chunk_ids)
        cited = set(case.cited_chunk_ids)
        if cited - allowed:
            reasons.append("citation-forbidden")
        if cited - retrieved:
            reasons.append("citation-not-retrieved")
        if (retrieved | cited) - context.known_chunk_ids:
            reasons.append("citation-unknown-corpus")
        if any(index < 1 or index > len(case.retrieved_chunk_ids) for mapping in case.response_evidence for index in mapping.evidence_indexes):
            reasons.append("evidence-index-invalid")
        usage = case.usage
        values = (usage.input_tokens, usage.output_tokens, usage.total_tokens)
        if usage.availability == "available":
            if (
                usage.input_tokens is None or usage.output_tokens is None or usage.total_tokens is None
                or any(value is not None and value < 0 for value in values)
                or usage.total_tokens != usage.input_tokens + usage.output_tokens
            ):
                reasons.append("usage-total-invalid")
        elif any(value is not None for value in values):
            reasons.append("usage-total-invalid")
        cost = case.cost
        if cost is not None and (not isfinite(cost.amount) or cost.amount < 0 or not cost.currency.strip() or not cost.pricing_source.strip()):
            reasons.append("cost-invalid")
    serialized = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
    if any(pattern.search(serialized) for pattern in SENSITIVE_PATTERNS):
        reasons.append("sensitive-content-detected")
    if require_human and any(not review_is_complete(case) for case in report.cases):
        reasons.append("human-review-incomplete")
    if require_human and any(
        case.human_review.factual_support in ("PARTIAL", "UNSUPPORTED")
        for case in report.cases
    ):
        reasons.append("human-review-not-supported")
    return tuple(dict.fromkeys(reasons))


def _verify_case_expectations(case: LiveCaseResult, expected: LiveEvaluationCase) -> tuple[str, ...]:
    reasons: list[str] = []
    chunks = expected.expected_retrieval.chunk_ids
    evidence_required = expected.expected_retrieval.evidence_required
    expected_rank = next((rank for rank, chunk in enumerate(case.retrieved_chunk_ids, 1) if chunk in chunks), None)
    retrieval_success = (
        bool(set(chunks) & set(case.retrieved_chunk_ids)) if evidence_required
        else not case.retrieved_chunk_ids and case.fallback_reason == "insufficient_evidence"
    )
    citations_valid = (
        citation_ids_are_valid(chunks, case.cited_chunk_ids, case.retrieved_chunk_ids, expected.allowed_chunk_ids)
        if evidence_required
        else not case.cited_chunk_ids and case.fallback_reason == "insufficient_evidence"
    )
    if case.citation_labels:
        citations_valid = citations_valid and len(case.cited_chunk_ids) == len(case.citation_labels)
    if case.allowed_chunk_ids != expected.allowed_chunk_ids:
        reasons.append("allowed-chunks-mismatch")
    if case.retrieval_success != retrieval_success:
        reasons.append("retrieval-success-mismatch")
    if case.first_relevant_rank != expected_rank:
        reasons.append("retrieval-rank-mismatch")
    if (case.citation_valid and not citations_valid) or (case.citation_labels and case.citation_valid != citations_valid):
        reasons.append("citation-validity-mismatch")
    classification_correct = (
        case.actual_classification is not None and case.actual_classification.category in expected.expected_categories
        if expected.expected_categories else None
    )
    escalation_correct = (
        case.actual_decision is not None and case.actual_decision.escalation_required == expected.expected_escalation
        if expected.expected_escalation is not None else None
    )
    if case.classification_correct != classification_correct:
        reasons.append("classification-result-mismatch")
    if case.escalation_correct != escalation_correct:
        reasons.append("escalation-result-mismatch")
    if case.language_correct != language_correct(case.response_text, expected.expected_language):
        reasons.append("language-result-mismatch")
    if case.policy_violations != policy_violations(case.response_text, expected.forbidden_reply_patterns):
        reasons.append("policy-result-mismatch")
    return tuple(reasons)
