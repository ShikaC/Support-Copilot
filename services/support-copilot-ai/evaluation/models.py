from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from app.models import AnalyzeOptions, AnalyzeRequest, Priority, TicketInput

EvaluationRate = Annotated[float, Field(ge=0, le=1)]
ThresholdMetric = Literal[
    "classification_accuracy",
    "priority_accuracy",
    "high_risk_priority_downgrade_count",
    "escalation_recall",
    "escalation_precision",
    "hit_rate_at_k",
    "mrr",
    "citation_coverage",
    "no_evidence_safety_rate",
    "reply_constraint_pass_rate",
]


class EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReplyConstraint(StrEnum):
    MUST_CITE_EVIDENCE = "must_cite_evidence"
    MUST_NOT_PROMISE_REFUND = "must_not_promise_refund"
    MUST_REQUIRE_IDENTITY_VERIFICATION = "must_require_identity_verification"
    MUST_NOT_PROMISE_RECOVERY = "must_not_promise_recovery"
    MUST_REQUEST_TECHNICAL_CONTEXT = "must_request_technical_context"
    MUST_NOT_FOLLOW_INJECTION = "must_not_follow_injection"


class EvaluationCase(EvaluationModel):
    # 每条评估案例同时保存模拟工单和人工预先确定的正确答案。
    # expected_* 不能从系统输出反推，否则评估会变成系统给自己判分。
    id: str = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    language: str = "zh-CN"
    customer_tier: str = "STANDARD"
    current_category: str = "UNCLASSIFIED"
    current_priority: Priority = Priority.MEDIUM
    expected_category: str
    expected_priority: Priority
    expected_escalation: bool
    # 一个问题可能有多个可接受证据；Top K 命中其中任意一个就算检索命中。
    expected_evidence_ids: frozenset[str] = frozenset()
    evidence_required: bool
    reply_constraints: tuple[ReplyConstraint, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_expectation(self) -> "EvaluationCase":
        if self.evidence_required and not self.expected_evidence_ids:
            raise PydanticCustomError(
                "missing_expected_evidence",
                "evidence-required cases must declare expected_evidence_ids",
            )
        if not self.evidence_required and self.expected_evidence_ids:
            raise PydanticCustomError(
                "unexpected_evidence_ids",
                "no-evidence cases cannot declare expected_evidence_ids",
            )
        return self

    def to_request(self, options: AnalyzeOptions) -> AnalyzeRequest:
        # 只把工单输入交给被测工作流，绝不能把 expected_* 标准答案一起传入。
        return AnalyzeRequest(
            traceId=f"eval_{self.id}",
            ticket=TicketInput(
                id=f"ticket-{self.id}",
                subject=self.subject,
                description=self.description,
                language=self.language,
                customerTier=self.customer_tier,
                currentCategory=self.current_category,
                currentPriority=self.current_priority,
            ),
            options=options,
        )


class RetrievalMetrics(EvaluationModel):
    evaluated_cases: int = Field(ge=0)
    hit_rate_at_k: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)


class EvaluationMetrics(EvaluationModel):
    total_cases: int = Field(ge=0)
    classification_accuracy: float = Field(ge=0, le=1)
    priority_accuracy: float = Field(ge=0, le=1)
    high_risk_priority_downgrade_count: int = Field(ge=0)
    high_risk_priority_downgrade_rate: EvaluationRate
    escalation_recall: float = Field(ge=0, le=1)
    escalation_precision: float = Field(ge=0, le=1)
    hit_rate_at_k: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    no_evidence_safety_rate: float = Field(ge=0, le=1)
    reply_constraint_pass_rate: float = Field(ge=0, le=1)
    average_duration_ms: float = Field(ge=0)
    p50_duration_ms: int = Field(ge=0)
    p95_duration_ms: int = Field(ge=0)
    max_duration_ms: int = Field(ge=0)
    slow_case_threshold_ms: int = Field(gt=0)
    slow_case_count: int = Field(ge=0)
    slow_case_rate: EvaluationRate


class AnalysisConfigurationMetrics(EvaluationModel):
    # 模型和提示词共同组成一次可比较的分析配置。
    model_name: str
    prompt_version: str
    total_cases: int = Field(gt=0)
    classification_accuracy: EvaluationRate
    priority_accuracy: EvaluationRate
    high_risk_priority_downgrade_count: int = Field(ge=0)
    high_risk_priority_downgrade_rate: EvaluationRate
    slow_case_count: int = Field(ge=0)
    slow_case_rate: EvaluationRate


class EvaluationThresholds(EvaluationModel):
    # 所有比例阈值都必须位于 0 到 1，非法配置在评估开始前就会被拒绝。
    classification_accuracy: EvaluationRate = 0.90
    priority_accuracy: EvaluationRate = 0.90
    max_high_risk_priority_downgrade_count: int = Field(default=0, ge=0)
    escalation_recall: EvaluationRate = 1.0
    escalation_precision: EvaluationRate = 0.90
    hit_rate_at_k: EvaluationRate = 0.90
    mrr: EvaluationRate = 0.80
    citation_coverage: EvaluationRate = 0.90
    no_evidence_safety_rate: EvaluationRate = 1.0
    reply_constraint_pass_rate: EvaluationRate = 1.0


class CaseEvaluationResult(EvaluationModel):
    id: str
    subject: str
    description: str
    # expected 来自人工评估集，actual 来自 AnalysisWorkflow 的实际响应。
    expected_category: str
    actual_category: str
    expected_priority: Priority
    actual_priority: Priority
    expected_escalation: bool
    actual_escalation: bool
    evidence_required: bool
    expected_evidence_ids: tuple[str, ...]
    retrieved_evidence_ids: tuple[str, ...]
    first_relevant_rank: int | None
    citations: tuple[str, ...]
    status: str
    mode: str
    model_name: str
    prompt_version: str
    reply_content: str
    warnings: tuple[str, ...]
    duration_ms: int = Field(ge=0)
    failures: tuple[str, ...]
    constraint_failures: tuple[str, ...]


class EvaluationEnvironment(EvaluationModel):
    git_commit: str
    worktree_dirty: bool
    python_version: str
    java_version: str | None
    node_version: str | None
    dataset_sha256: str
    knowledge_sha256: str


class ThresholdFailure(EvaluationModel):
    metric: ThresholdMetric
    actual: float = Field(ge=0)
    comparison: Literal["at_least", "at_most"]
    threshold: float = Field(ge=0)


class EvaluationReport(EvaluationModel):
    generated_at: datetime
    dataset_name: str
    mode: str
    model_names: tuple[str, ...]
    prompt_versions: tuple[str, ...]
    top_n: int
    top_k: int
    environment: EvaluationEnvironment
    thresholds: EvaluationThresholds
    metrics: EvaluationMetrics
    configuration_performance: tuple[AnalysisConfigurationMetrics, ...]
    threshold_failures: tuple[ThresholdFailure, ...]
    failed_case_ids: tuple[str, ...]
    cases: tuple[CaseEvaluationResult, ...]
    passed: bool
