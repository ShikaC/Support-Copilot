import logging
import time
from typing import assert_never
import uuid
from datetime import UTC, datetime

from app.config import Settings
from app.errors import (
    FallbackReason,
    LiveProviderConfigurationError,
    RecoverableAiError,
)
from app.knowledge import KnowledgeRetriever, RetrievalRequest
from app.local_analysis import LocalAnalysisPolicy, WorkflowObservation
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Classification,
    Retrieval,
    Usage,
)
from app.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class AnalysisWorkflow:
    def __init__(self, settings: Settings, retriever: KnowledgeRetriever) -> None:
        self._settings = settings
        self._retriever = retriever
        self._provider = OpenAIProvider(settings) if settings.live_ready else None
        self._local_policy = LocalAnalysisPolicy()

    async def run(self, request: AnalyzeRequest) -> AnalyzeResponse:
        started = time.perf_counter()
        live = self._settings.effective_mode == "live"
        mode = "live" if live else "mock"

        try:
            # AI 工作流有三个可见输出：
            # 分类结果、检索证据和回复建议。
            # 页面展示这些可审计结果，而不是假装展示模型隐藏推理。
            query = self._build_query(request)
            retrieval_started = time.perf_counter()
            hits = await self._retriever.search(
                RetrievalRequest(
                    ticket=request.ticket,
                    query=query,
                    top_n=request.options.top_n,
                    top_k=request.options.top_k,
                    live=live,
                    knowledge_access=request.knowledge_access,
                )
            )
            retrieval_ms = self._elapsed_ms(retrieval_started)

            evidence_missing = len(hits) == 0
            generation_started = time.perf_counter()
            if evidence_missing:
                # 没有证据时不把空上下文交给模型，避免模型先生成再被动标记 fallback。
                draft = self._local_policy.draft(request, hits)
                input_tokens, output_tokens = 0, 0
                mode = "fallback"
            elif live:
                if self._provider is None:
                    raise LiveProviderConfigurationError
                draft, input_tokens, output_tokens = await self._provider.analyze(
                    request,
                    hits,
                )
                self._retriever.readiness.record_live_generation_success()
            else:
                draft = self._local_policy.draft(request, hits)
                input_tokens, output_tokens = 0, 0
            generation_ms = self._elapsed_ms(generation_started)

            decision = self._local_policy.decision(draft.category, evidence_missing)
            reply = self._local_policy.reply(draft, hits, evidence_missing)
            total_ms = self._elapsed_ms(started)
            model_name = (
                self._settings.openai_chat_model
                if live and not evidence_missing
                else "deterministic-demo"
            ) or "deterministic-demo"

            response = AnalyzeResponse(
                id=self._id("run"),
                trace_id=request.trace_id,
                status="FALLBACK" if evidence_missing else "SUCCEEDED",
                mode=mode,
                fallback_reason=(
                    FallbackReason.INSUFFICIENT_EVIDENCE if evidence_missing else None
                ),
                model_name=model_name,
                prompt_version=request.options.prompt_version,
                classification=Classification(
                    intent=draft.intent,
                    category=draft.category,
                    priority=draft.priority,
                    sentiment=draft.sentiment,
                    confidence=draft.confidence,
                    reason_summary=draft.reason_summary,
                ),
                workflow_steps=self._local_policy.workflow_steps(
                    WorkflowObservation(
                        retrieval_ms=retrieval_ms,
                        generation_ms=generation_ms,
                        hit_count=len(hits),
                        evidence_missing=evidence_missing,
                    )
                ),
                retrieval=Retrieval(query=query, hits=hits),
                suggested_reply=reply,
                decision=decision,
                usage=Usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=total_ms,
                ),
                created_at=datetime.now(UTC),
            )
            logger.info(
                "analysis.completed",
                extra={
                    "trace_id": request.trace_id,
                    "mode": response.mode,
                    "status": response.status,
                    "hit_count": len(hits),
                },
            )
            return response
        # 只有经过外部依赖边界确认的可恢复错误才会降级。
        # RuntimeError、AttributeError 等程序缺陷会继续抛出并留下真实错误信息。
        except RecoverableAiError as exc:
            if not live:
                raise
            match exc.operation:
                case "embedding":
                    self._retriever.readiness.record_live_retrieval_failure()
                case "structured_generation":
                    self._retriever.readiness.record_live_generation_failure()
                case unreachable:
                    assert_never(unreachable)
            logger.warning(
                "analysis.external_failure",
                extra={
                    "trace_id": request.trace_id,
                    "error_type": type(exc).__name__,
                },
            )
            return await self._fallback_after_error(
                request,
                started,
                exc.fallback_reason,
            )

    async def _fallback_after_error(
        self,
        request: AnalyzeRequest,
        started: float,
        fallback_reason: FallbackReason,
    ) -> AnalyzeResponse:
        query = self._build_query(request)
        hits = await self._retriever.search(
            RetrievalRequest(
                ticket=request.ticket,
                query=query,
                top_n=request.options.top_n,
                top_k=request.options.top_k,
                live=False,
                knowledge_access=request.knowledge_access,
            )
        )
        draft = self._local_policy.draft(request, hits)
        decision = self._local_policy.decision(
            draft.category,
            len(hits) == 0,
            force_escalation=True,
        )
        response = AnalyzeResponse(
            id=self._id("run"),
            trace_id=request.trace_id,
            status="FALLBACK",
            mode="fallback",
            fallback_reason=fallback_reason,
            model_name="deterministic-demo-fallback",
            prompt_version=request.options.prompt_version,
            classification=Classification(
                intent=draft.intent,
                category=draft.category,
                priority=draft.priority,
                sentiment=draft.sentiment,
                confidence=min(draft.confidence, 0.68),
                reason_summary="实时模型调用失败，已使用本地规则生成可审核结果。",
            ),
            workflow_steps=self._local_policy.workflow_steps(
                WorkflowObservation(
                    retrieval_ms=0,
                    generation_ms=0,
                    hit_count=len(hits),
                    evidence_missing=len(hits) == 0,
                    failed_live=True,
                )
            ),
            retrieval=Retrieval(query=query, hits=hits),
            suggested_reply=self._local_policy.reply(draft, hits, len(hits) == 0),
            decision=decision,
            usage=Usage(duration_ms=self._elapsed_ms(started)),
            created_at=datetime.now(UTC),
        )
        logger.warning(
            "analysis.fallback",
            extra={
                "trace_id": request.trace_id,
                "mode": response.mode,
                "status": response.status,
                "hit_count": len(hits),
                "reason": fallback_reason.value,
            },
        )
        return response

    def _build_query(self, request: AnalyzeRequest) -> str:
        ticket = request.ticket
        return f"{ticket.subject} {ticket.description[:180]}".strip()

    def _elapsed_ms(self, started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))

    def _id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"
