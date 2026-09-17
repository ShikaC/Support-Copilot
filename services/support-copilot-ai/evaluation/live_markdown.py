from evaluation.live_models import LiveEvaluationReport


def render_live_markdown(report: LiveEvaluationReport) -> str:
    lines = [
        "# Live evaluation report",
        "",
        "> These are evaluation results for this dataset/run only. They are not production accuracy, an SLO, or a stability claim.",
        "",
        f"- Run: `{report.run.run_id}`",
        f"- Timestamp: `{report.run.timestamp.isoformat()}`",
        f"- Dataset: `{report.run.dataset_id}` v`{report.run.dataset_version}` (`{report.run.dataset_checksum}`)",
        f"- Git: `{report.run.git_commit}`; dirty=`{str(report.run.worktree_dirty).lower()}`",
        f"- Knowledge release: `{report.provenance.knowledge_release_id}` v`{report.provenance.knowledge_release_version}`",
        f"- Semantic corpus checksum: `{report.provenance.semantic_corpus_checksum}`",
        f"- Chat: `{report.provenance.chat_provider_identity}` / `{report.provenance.chat_model}` / `{report.provenance.chat_protocol}`",
        f"- Prompt: `{report.run.prompt_version}`",
        f"- Runtime source SHA-256: `{report.run.runtime_source_sha256 or 'not captured (legacy report)'}`",
        f"- Publishable: `{str(report.summary.publishable).lower()}`",
        f"- Gate reasons: `{', '.join(report.summary.gate_reasons) or 'none'}`",
        "",
        "## Evaluation Results",
        "",
        f"- Cases: `{report.summary.total_cases}`",
        f"- Succeeded: `{report.summary.succeeded_cases}`",
        f"- Retrieval success: `{report.summary.retrieval_success_count}/{report.summary.total_cases}`",
        f"- MRR: `{report.summary.mean_reciprocal_rank:.3f}`",
        f"- Citation valid: `{report.summary.citation_valid_count}/{report.summary.total_cases}`",
        f"- No-evidence safety rate: `{report.summary.no_evidence_safety_rate:.3f}`",
        f"- Fallback: `{report.summary.fallback_count}`",
        f"- Average/p95 runner latency: `{report.summary.average_latency_ms:.1f} ms` / `{report.summary.p95_latency_ms} ms`",
        f"- p95 method: `{report.summary.p95_method}`",
        f"- Human reviewed: `{report.summary.human_reviewed_count}/{report.summary.total_cases}`",
        "",
        "## Cases",
        "",
    ]
    for case in report.cases:
        lines.extend([
            f"### {case.case_id}",
            f"- Status/mode: `{case.status}` / `{case.mode}`",
            f"- Retrieval success: `{str(case.retrieval_success).lower()}`",
            f"- Citation valid: `{str(case.citation_valid).lower()}`",
            f"- Language script check: `{case.language_correct}`",
            f"- Policy pattern matches: `{', '.join(case.policy_violations) or 'none'}`",
            f"- Reply warnings: `{'; '.join(case.reply_warnings) or 'none'}`",
            f"- Latency: `{case.latency_ms} ms`",
            f"- Token usage: `{case.usage.availability}`",
            f"- Cost: `{'unavailable' if case.cost is None else case.cost.amount}`",
            f"- Human factual support: `{case.human_review.factual_support}`",
            "",
        ])
    return "\n".join(lines)
