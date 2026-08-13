from typing import assert_never

from evaluation.models import (
    CaseFailure,
    CaseEvaluationResult,
    EvaluationReport,
    ThresholdFailure,
    ThresholdMetric,
)

def render_markdown(report: EvaluationReport) -> str:
    metrics = report.metrics
    failed_case_lines = _render_failed_cases(report.cases)
    threshold_failure_lines = [
        _render_threshold_failure(failure)
        for failure in report.threshold_failures
    ] or ["无"]
    configuration_performance_rows = [
        (
            f"| {configuration.model_name} | {configuration.prompt_version} | "
            f"{configuration.total_cases} | "
            f"{configuration.classification_accuracy:.3f} | "
            f"{configuration.priority_accuracy:.3f} | "
            f"{configuration.high_risk_priority_downgrade_count} | "
            f"{configuration.high_risk_priority_downgrade_rate:.3f} | "
            f"{configuration.slow_case_count} | "
            f"{configuration.slow_case_rate:.3f} |"
        )
        for configuration in report.configuration_performance
    ]
    lines = [
        "# Support-Copilot Mock 评估报告",
        "",
        f"> 生成时间：{report.generated_at.isoformat()}",
        f"> 数据集：{report.dataset_name}",
        f"> 模式：{report.mode}",
        f"> 模型：{', '.join(report.model_names)}",
        f"> 提示词版本：{', '.join(report.prompt_versions)}",
        f"> 结论：{'通过' if report.passed else '未通过'}",
        "",
        "## 运行环境",
        "",
        f"- Git commit：{report.environment.git_commit}",
        f"- 工作区有未提交改动：{report.environment.worktree_dirty}",
        f"- Python：{report.environment.python_version}",
        f"- Java：{report.environment.java_version or '未检测'}",
        f"- Node.js：{report.environment.node_version or '未检测'}",
        f"- topN/topK：{report.top_n}/{report.top_k}",
        "",
        "## 指标",
        "",
        "| 指标 | 结果 |",
        "| --- | ---: |",
        f"| 分类准确率 | {metrics.classification_accuracy:.3f} |",
        f"| 优先级准确率 | {metrics.priority_accuracy:.3f} |",
        f"| 高风险优先级降级数量 | {metrics.high_risk_priority_downgrade_count} |",
        f"| 高风险优先级降级比例 | {metrics.high_risk_priority_downgrade_rate:.3f} |",
        (
            "| 允许最大高风险降级数量 | "
            f"{report.thresholds.max_high_risk_priority_downgrade_count} |"
        ),
        f"| 升级召回率 | {metrics.escalation_recall:.3f} |",
        f"| 升级准确率 | {metrics.escalation_precision:.3f} |",
        f"| Hit@{report.top_k} | {metrics.hit_rate_at_k:.3f} |",
        f"| MRR | {metrics.mrr:.3f} |",
        f"| 引用覆盖率 | {metrics.citation_coverage:.3f} |",
        f"| 无证据安全率 | {metrics.no_evidence_safety_rate:.3f} |",
        f"| 回复约束通过率 | {metrics.reply_constraint_pass_rate:.3f} |",
        f"| 平均耗时（毫秒） | {metrics.average_duration_ms:.1f} |",
        f"| P50 耗时（毫秒） | {metrics.p50_duration_ms} |",
        f"| P95 耗时（毫秒） | {metrics.p95_duration_ms} |",
        f"| 最大耗时（毫秒） | {metrics.max_duration_ms} |",
        f"| 慢案例标准（毫秒） | > {metrics.slow_case_threshold_ms} |",
        f"| 慢案例数量 | {metrics.slow_case_count} |",
        f"| 慢案例比例 | {metrics.slow_case_rate:.3f} |",
        "",
        "## 分析配置性能",
        "",
        "| 模型 | 提示词版本 | 总案例数 | 分类准确率 | 优先级准确率 | 高风险降级数 | 高风险降级比例 | 慢案例数 | 慢案例比例 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *configuration_performance_rows,
        "",
        "## 失败门槛",
        "",
        *threshold_failure_lines,
        "",
        "## 失败样例",
        "",
        *failed_case_lines,
        "",
        "## 说明",
        "",
        "本报告只评估本地确定性 mock 工作流，不代表 live 模型或生产 RAG 效果。",
        "指标只能解释当前固定评估集，不能外推为通用准确率。",
    ]
    return "\n".join(lines) + "\n"


def _render_failed_cases(
    cases: tuple[CaseEvaluationResult, ...],
) -> list[str]:
    lines: list[str] = []
    for case in cases:
        if not case.failures:
            continue
        if lines:
            lines.append("")
        lines.append(f"### {case.id} - {case.subject}")
        lines.extend(_render_case_failure(failure) for failure in case.failures)
    return lines or ["无"]


def _render_case_failure(failure: CaseFailure) -> str:
    match failure.metric:
        case "classification":
            return f"- 分类：预期 {failure.expected}，实际 {failure.actual}"
        case "priority":
            return f"- 优先级：预期 {failure.expected}，实际 {failure.actual}"
        case "escalation":
            return f"- 人工升级：预期 {failure.expected}，实际 {failure.actual}"
        case "citation":
            return "- 引用：已检索到相关证据，但回复没有引用"
        case "no_evidence_safety":
            return "- 无证据安全：未使用无引用并升级人工复核的 fallback"
        case "reply_constraint":
            return f"- 回复约束：未满足 {failure.expected}"
        case unreachable:
            assert_never(unreachable)


def _render_threshold_failure(failure: ThresholdFailure) -> str:
    metric = failure.metric
    label = _threshold_label(metric)
    match failure.comparison:
        case "at_least":
            comparison = "至少"
        case "at_most":
            comparison = "最多"
        case unreachable:
            assert_never(unreachable)
    actual = _format_threshold_value(metric, failure.actual)
    threshold = _format_threshold_value(metric, failure.threshold)
    return f"- {label}：实际 {actual}，要求{comparison} {threshold}"


def _format_threshold_value(metric: ThresholdMetric, value: float) -> str:
    if metric.endswith("_count"):
        return str(round(value))
    return f"{value:.3f}"


def _threshold_label(metric: ThresholdMetric) -> str:
    match metric:
        case "classification_accuracy":
            return "分类准确率"
        case "priority_accuracy":
            return "优先级准确率"
        case "high_risk_priority_downgrade_count":
            return "高风险优先级降级数量"
        case "escalation_recall":
            return "升级召回率"
        case "escalation_precision":
            return "升级准确率"
        case "hit_rate_at_k":
            return "检索命中率"
        case "mrr":
            return "MRR"
        case "citation_coverage":
            return "引用覆盖率"
        case "no_evidence_safety_rate":
            return "无证据安全率"
        case "reply_constraint_pass_rate":
            return "回复约束通过率"
        case unreachable:
            assert_never(unreachable)
