from datetime import datetime
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError

from app.errors import FallbackReason

PromptVersion = Literal["ticket-analysis-v1"]
TRACE_ID_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$"


class ApiModel(BaseModel):
    # Java 发送的是 camelCase JSON；Python 内部仍使用 snake_case 字段名。
    # extra="forbid" 会拒绝契约中不存在的字段，避免错误数据悄悄流入工作流。
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Sentiment(StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class SupportScope(StrEnum):
    GENERAL = "GENERAL"
    BILLING = "BILLING"
    ACCOUNT = "ACCOUNT"
    PRIVACY = "PRIVACY"
    TECHNICAL = "TECHNICAL"


class KnowledgeAccess(ApiModel):
    model_config = ConfigDict(frozen=True)

    release_id: str = Field(min_length=1, pattern=r".*\S.*")
    release_version: int = Field(gt=0)
    corpus_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed_scopes: tuple[SupportScope, ...]


BUNDLED_RELEASE_ID: Final = "support-copilot-bundled-v1"
BUNDLED_RELEASE_VERSION: Final = 1
BUNDLED_CORPUS_CHECKSUM: Final = (
    "b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874"
)
BUNDLED_KNOWLEDGE_ACCESS: Final = KnowledgeAccess(
    release_id=BUNDLED_RELEASE_ID,
    release_version=BUNDLED_RELEASE_VERSION,
    corpus_checksum=BUNDLED_CORPUS_CHECKSUM,
    allowed_scopes=tuple(SupportScope),
)


class TicketInput(ApiModel):
    # Python 分析的是工单内容，不只是一条工单 ID。
    # 标题和描述不能为空，并限制长度，避免无效或过大的输入进入 AI 流程。
    id: str
    subject: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    language: str = "zh-CN"
    customer_tier: str = "STANDARD"
    current_category: str = "UNCLASSIFIED"
    current_priority: Priority = Priority.MEDIUM


class AnalyzeOptions(ApiModel):
    top_n: int = Field(default=10, ge=1, le=30)
    top_k: int = Field(default=3, ge=1, le=10)
    prompt_version: PromptVersion = "ticket-analysis-v1"

    @model_validator(mode="after")
    def validate_retrieval_window(self) -> "AnalyzeOptions":
        # 最终证据只能从第一轮候选中选出，因此 top_k 不能超过 top_n。
        if self.top_k > self.top_n:
            raise PydanticCustomError(
                "top_k_exceeds_top_n",
                "topK must be less than or equal to topN",
            )
        return self


class AnalyzeRequest(ApiModel):
    # Java 调用 /analyze 时必须交付：追踪标识、完整工单和检索选项。
    trace_id: str = Field(pattern=TRACE_ID_PATTERN)
    ticket: TicketInput
    knowledge_access: KnowledgeAccess
    options: AnalyzeOptions = AnalyzeOptions()


class Classification(ApiModel):
    intent: str
    category: str
    priority: Priority
    sentiment: Sentiment
    confidence: float = Field(ge=0, le=1)
    reason_summary: str = Field(max_length=240)


class WorkflowStep(ApiModel):
    id: str
    name: str
    description: str
    status: Literal["complete", "running", "pending", "failed"]
    duration_ms: int | None = Field(default=None, ge=0)


class RetrievalHit(ApiModel):
    chunk_id: str
    document_id: str
    document_title: str
    section: str
    content: str
    source_uri: str
    retrieval_method: str
    # initial_rank 是第一轮召回名次，数字越小表示初始排名越靠前。
    initial_rank: int
    initial_score: float
    # rerank_position 是调整后的最终名次，页面展示和 MRR 评估应使用最终名次。
    rerank_position: int
    rerank_score: float
    used_as_evidence: bool


class Retrieval(ApiModel):
    query: str
    hits: list[RetrievalHit]


class SuggestedReply(ApiModel):
    content: str
    citations: list[str]
    warnings: list[str]


class Decision(ApiModel):
    escalation_required: bool
    reason: str


class Usage(ApiModel):
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0


class AnalyzeResponse(ApiModel):
    id: str
    trace_id: str
    status: Literal["RUNNING", "SUCCEEDED", "FAILED", "FALLBACK"]
    mode: Literal["live", "mock", "fallback"]
    fallback_reason: FallbackReason | None
    model_name: str
    prompt_version: str
    classification: Classification
    workflow_steps: list[WorkflowStep]
    retrieval: Retrieval
    suggested_reply: SuggestedReply
    decision: Decision
    usage: Usage
    created_at: datetime


class ModelDraft(BaseModel):
    """Schema returned by the OpenAI structured-output request."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    category: str
    priority: Priority
    sentiment: Sentiment
    confidence: float = Field(ge=0, le=1)
    reason_summary: str = Field(max_length=240)
    reply_content: str
    warnings: list[str]
    # 模型只能引用输入证据中的 1-based 序号，系统会在回复落地前校验这些序号。
    citation_indexes: list[int] = Field(default_factory=list)
