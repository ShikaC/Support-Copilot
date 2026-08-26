import json
import re
from math import isfinite
from typing import Final

from evaluation.live_models import LiveEvaluationReport, VerificationContext

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
    for case in report.cases:
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
            complete = all(value is not None and value >= 0 for value in values)
            if not complete:
                reasons.append("usage-total-invalid")
            elif usage.total_tokens != usage.input_tokens + usage.output_tokens:
                reasons.append("usage-total-invalid")
        elif any(value is not None for value in values):
            reasons.append("usage-total-invalid")
        cost = case.cost
        if cost is not None and (not isfinite(cost.amount) or cost.amount < 0 or not cost.currency.strip() or not cost.pricing_source.strip()):
            reasons.append("cost-invalid")
    serialized = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
    if any(pattern.search(serialized) for pattern in SENSITIVE_PATTERNS):
        reasons.append("sensitive-content-detected")
    if require_human and any(
        case.human_review.factual_support == "NOT_REVIEWED"
        or not case.human_review.reviewer
        or not case.human_review.decision_note
        or case.human_review.reviewed_at is None
        for case in report.cases
    ):
        reasons.append("human-review-incomplete")
    return tuple(dict.fromkeys(reasons))
