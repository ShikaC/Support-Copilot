from evaluation.models import EvaluationReport


def render_markdown(report: EvaluationReport) -> str:
    metrics = report.metrics
    failed_cases = "、".join(report.failed_case_ids) or "无"
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
        "## 失败样例",
        "",
        failed_cases,
        "",
        "## 说明",
        "",
        "本报告只评估本地确定性 mock 工作流，不代表 live 模型或生产 RAG 效果。",
        "指标只能解释当前固定评估集，不能外推为通用准确率。",
    ]
    return "\n".join(lines) + "\n"
