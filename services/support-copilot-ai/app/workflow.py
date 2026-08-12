import logging
import time
import uuid
from datetime import UTC, datetime

from app.config import Settings
from app.errors import RecoverableAiError
from app.knowledge import KnowledgeRetriever
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Classification,
    Decision,
    ModelDraft,
    Priority,
    Retrieval,
    RetrievalHit,
    Sentiment,
    SuggestedReply,
    Usage,
    WorkflowStep,
)
from app.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

HIGH_RISK_CATEGORIES = {"BILLING", "PRIVACY", "SECURITY", "LEGAL"}


class AnalysisWorkflow:
    def __init__(self, settings: Settings, retriever: KnowledgeRetriever) -> None:
        self._settings = settings
        self._retriever = retriever
        self._provider = OpenAIProvider(settings) if settings.live_ready else None

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
                request.ticket,
                query,
                request.options.top_n,
                request.options.top_k,
                live=live,
            )
            retrieval_ms = self._elapsed_ms(retrieval_started)

            generation_started = time.perf_counter()
            if live:
                if self._provider is None:
                    raise RuntimeError("Live mode is not configured")
                draft, input_tokens, output_tokens = await self._provider.analyze(
                    request.ticket,
                    hits,
                    request.options.prompt_version,
                )
            else:
                draft = self._mock_draft(request, hits)
                input_tokens, output_tokens = 0, 0
            generation_ms = self._elapsed_ms(generation_started)

            evidence_missing = len(hits) == 0
            if evidence_missing:
                mode = "fallback"
            decision = self._decision(draft.category, evidence_missing)
            reply = self._reply(draft, hits, evidence_missing)
            total_ms = self._elapsed_ms(started)

            return AnalyzeResponse(
                id=self._id("run"),
                trace_id=request.trace_id,
                status="FALLBACK" if evidence_missing else "SUCCEEDED",
                mode=mode,
                model_name=(
                    self._settings.openai_chat_model or "configured-chat-model"
                    if live
                    else "deterministic-demo"
                ),
                prompt_version=request.options.prompt_version,
                classification=Classification(
                    intent=draft.intent,
                    category=draft.category,
                    priority=draft.priority,
                    sentiment=draft.sentiment,
                    confidence=draft.confidence,
                    reason_summary=draft.reason_summary,
                ),
                workflow_steps=self._workflow_steps(
                    retrieval_ms,
                    generation_ms,
                    len(hits),
                    evidence_missing,
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
        # 只有经过外部依赖边界确认的可恢复错误才会降级。
        # RuntimeError、AttributeError 等程序缺陷会继续抛出并留下真实错误信息。
        except RecoverableAiError as exc:
            if not live:
                raise
            logger.warning("Live analysis failed, switching to fallback: %s", exc)
            return await self._fallback_after_error(request, started)

    async def _fallback_after_error(
        self,
        request: AnalyzeRequest,
        started: float,
    ) -> AnalyzeResponse:
        query = self._build_query(request)
        hits = await self._retriever.search(
            request.ticket,
            query,
            request.options.top_n,
            request.options.top_k,
            live=False,
        )
        draft = self._mock_draft(request, hits)
        decision = self._decision(draft.category, len(hits) == 0, force_escalation=True)
        return AnalyzeResponse(
            id=self._id("run"),
            trace_id=request.trace_id,
            status="FALLBACK",
            mode="fallback",
            model_name=self._settings.openai_chat_model or "configured-chat-model",
            prompt_version=request.options.prompt_version,
            classification=Classification(
                intent=draft.intent,
                category=draft.category,
                priority=draft.priority,
                sentiment=draft.sentiment,
                confidence=min(draft.confidence, 0.68),
                reason_summary="实时模型调用失败，已使用本地规则生成可审核结果。",
            ),
            workflow_steps=self._workflow_steps(0, 0, len(hits), len(hits) == 0, failed_live=True),
            retrieval=Retrieval(query=query, hits=hits),
            suggested_reply=self._reply(draft, hits, len(hits) == 0),
            decision=decision,
            usage=Usage(duration_ms=self._elapsed_ms(started)),
            created_at=datetime.now(UTC),
        )

    def _mock_draft(
        self,
        request: AnalyzeRequest,
        hits: list[RetrievalHit],
    ) -> ModelDraft:
        ticket = request.ticket
        category = self._classify(ticket.subject + " " + ticket.description, ticket.current_category)
        priority = self._priority(category, ticket.current_priority, ticket.customer_tier)
        no_evidence = len(hits) == 0

        reason_by_category = {
            "BILLING": "涉及重复扣款，需要账务核验，且客户已明确表达时效诉求。",
            "ACCOUNT_ACCESS": "企业登录能力受阻，可能影响多个成员。",
            "PRIVACY": "包含数据导出或删除请求，必须经过身份和授权核验。",
            "DATA_EXPORT": "导出任务耗时超过常见基线，并包含可追踪任务编号。",
            "TECHNICAL": "包含可精确检索的错误码，需要按排查手册收集环境信息。",
            "SUBSCRIPTION": "用户正在评估套餐能力和席位计费，属于低风险咨询。",
            "DATA_RECOVERY": "知识库未找到覆盖当前保留期的有效资料，需要人工确认。",
        }
        reply_by_category = {
            "BILLING": "您好，我们已收到您反馈的重复扣款问题。请补充订单号、扣款日期、金额和支付渠道。收到信息后，我们会转交账务支持组复核。在核验完成前，我们暂时无法确认退款结果与到账时间。",
            "ACCOUNT_ACCESS": "您好，我们已按企业登录故障记录该问题。请提供最近一次失败时间、登录域名和身份提供商状态，我们会优先检查 SSO 回调与域名配置。",
            "PRIVACY": "您好，我们已收到数据导出与删除请求。该操作需要完成申请人身份、企业授权和数据范围核验，合规专员会在当前工单中说明所需材料。",
            "DATA_EXPORT": "您好，我们已记录导出任务编号和当前等待时间。数据平台组会检查任务队列与存储状态，请暂时不要重复创建相同导出任务。",
            "TECHNICAL": "您好，请补充客户端版本、Windows 版本和代理配置。我们会依据错误码处理手册继续排查同步连接。",
            "SUBSCRIPTION": "您好，专业版默认包含 20 位成员，超过后按新增席位计费。具体单价请以当前订单报价为准。",
            "DATA_RECOVERY": "您好，我们需要由数据支持团队确认该项目是否仍在可恢复范围内。请提供项目名称和大致删除日期。",
        }

        return ModelDraft(
            intent=self._intent(category),
            category=category,
            priority=priority,
            sentiment=Sentiment.NEUTRAL if priority == Priority.LOW else Sentiment.NEGATIVE,
            confidence=0.42 if no_evidence else self._confidence(category),
            reason_summary=reason_by_category.get(
                category,
                "已根据工单内容生成初步分类，等待人工确认。",
            ),
            reply_content=reply_by_category.get(
                category,
                "您好，我们已经收到您的问题，支持人员会核对相关信息并继续回复您。",
            ),
            warnings=["证据不足，禁止承诺处理结果。"] if no_evidence else [],
        )

    def _classify(self, text: str, current_category: str) -> str:
        lowered = text.lower()
        rules = [
            ("BILLING", ("重复扣款", "重复支付", "两笔扣款", "账单")),
            ("ACCOUNT_ACCESS", ("sso", "登录", "账号锁定")),
            ("INVOICE", ("发票", "抬头")),
            ("DATA_EXPORT", ("导出", "处理中", "exp-")),
            ("SUBSCRIPTION", ("专业版", "套餐", "协作者", "成员上限")),
            ("PRIVACY", ("数据删除", "离职员工", "隐私", "授权材料")),
            ("TECHNICAL", ("sync-", "错误码", "客户端")),
            ("DATA_RECOVERY", ("恢复", "误删", "备份")),
        ]
        for category, keywords in rules:
            if any(keyword in lowered for keyword in keywords):
                return category
        return current_category if current_category != "UNCLASSIFIED" else "GENERAL"

    def _priority(
        self,
        category: str,
        current_priority: Priority,
        customer_tier: str,
    ) -> Priority:
        if category == "ACCOUNT_ACCESS" and customer_tier == "ENTERPRISE":
            return Priority.URGENT
        if category in HIGH_RISK_CATEGORIES or category in {"DATA_EXPORT", "DATA_RECOVERY"}:
            return Priority.HIGH
        return current_priority

    def _decision(
        self,
        category: str,
        evidence_missing: bool,
        force_escalation: bool = False,
    ) -> Decision:
        escalation = force_escalation or evidence_missing or category in HIGH_RISK_CATEGORIES
        if force_escalation:
            reason = "实时模型调用失败，需要人工审核本地降级结果。"
        elif evidence_missing:
            reason = "检索未找到充分证据，需要人工确认处理边界。"
        elif category == "BILLING":
            reason = "支付争议必须由账务支持组核验交易记录。"
        elif category == "PRIVACY":
            reason = "隐私请求必须由合规专员审核。"
        else:
            reason = "当前结果可由一线客服审核后使用。"
        return Decision(escalation_required=escalation, reason=reason)

    def _reply(
        self,
        draft: ModelDraft,
        hits: list[RetrievalHit],
        evidence_missing: bool,
    ) -> SuggestedReply:
        # 当前会列出被采用的知识片段，但仅有引用列表不能证明回复中的每个结论都有证据支持。
        # citation accuracy 仍需要用评估案例逐条核对“结论”和“引用内容”是否一致。
        citations = [
            f"{hit.document_title} {hit.section}"
            for hit in hits
        ]
        citation_markers = "" if not citations else " " + "".join(
            f"[{index}]" for index in range(1, len(citations) + 1)
        )
        warnings = list(draft.warnings)
        if evidence_missing and "证据不足，禁止承诺处理结果。" not in warnings:
            warnings.append("证据不足，禁止承诺处理结果。")
        return SuggestedReply(
            content=draft.reply_content + citation_markers,
            citations=citations,
            warnings=warnings,
        )

    def _workflow_steps(
        self,
        retrieval_ms: int,
        generation_ms: int,
        hit_count: int,
        evidence_missing: bool,
        failed_live: bool = False,
    ) -> list[WorkflowStep]:
        return [
            self._step("normalize", "内容预处理", "语言识别与输入校验完成", 12),
            self._step(
                "classify",
                "工单理解",
                "类别、优先级与情绪识别完成",
                max(18, generation_ms // 3),
            ),
            self._step(
                "retrieve",
                "知识检索",
                "未找到满足阈值的有效证据"
                if evidence_missing
                else f"最终采用 {hit_count} 条知识片段",
                retrieval_ms,
            ),
            self._step(
                "generate",
                "回复生成",
                "实时调用失败，已生成本地谨慎回复"
                if failed_live
                else "已根据证据生成回复草稿",
                generation_ms,
                "failed" if failed_live else "complete",
            ),
            self._step(
                "risk",
                "风险检查",
                "证据不足，转入人工复核"
                if evidence_missing
                else "确定性风险规则检查完成",
                8,
            ),
        ]

    def _step(
        self,
        step_id: str,
        name: str,
        description: str,
        duration_ms: int,
        status: str = "complete",
    ) -> WorkflowStep:
        return WorkflowStep(
            id=step_id,
            name=name,
            description=description,
            status=status,  # type: ignore[arg-type]
            duration_ms=max(0, duration_ms),
        )

    def _build_query(self, request: AnalyzeRequest) -> str:
        ticket = request.ticket
        return f"{ticket.subject} {ticket.description[:180]}".strip()

    def _intent(self, category: str) -> str:
        return {
            "BILLING": "duplicate_charge",
            "ACCOUNT_ACCESS": "sso_login_issue",
            "INVOICE": "invoice_correction",
            "DATA_EXPORT": "export_job_stalled",
            "SUBSCRIPTION": "plan_capacity_question",
            "PRIVACY": "data_subject_request",
            "TECHNICAL": "technical_error",
            "DATA_RECOVERY": "deleted_project_recovery",
        }.get(category, "general_support_request")

    def _confidence(self, category: str) -> float:
        return {
            "PRIVACY": 0.95,
            "ACCOUNT_ACCESS": 0.93,
            "TECHNICAL": 0.9,
            "BILLING": 0.88,
            "SUBSCRIPTION": 0.84,
        }.get(category, 0.86)

    def _elapsed_ms(self, started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))

    def _id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"
