from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
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


class TicketInput(ApiModel):
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
    enable_rerank: bool = False
    prompt_version: str = "ticket-analysis-v1"


class AnalyzeRequest(ApiModel):
    trace_id: str
    ticket: TicketInput
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
    initial_rank: int
    initial_score: float
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
