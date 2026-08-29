from dataclasses import dataclass

from app.errors import InvalidModelResponseError
from app.models import (
    AnalyzeRequest,
    Decision,
    ModelDraft,
    Priority,
    RetrievalHit,
    Sentiment,
    SuggestedReply,
    WorkflowStep,
)

HIGH_RISK_CATEGORIES = {"BILLING", "PRIVACY", "SECURITY", "LEGAL"}


def citation_label(hit: RetrievalHit) -> str:
    return f"{hit.document_title} {hit.section} [chunkId:{hit.chunk_id}]"


@dataclass(frozen=True, slots=True)
class WorkflowObservation:
    retrieval_ms: int
    generation_ms: int
    hit_count: int
    evidence_missing: bool
    failed_live: bool = False


class LocalAnalysisPolicy:
    def draft(
        self,
        request: AnalyzeRequest,
        hits: list[RetrievalHit],
    ) -> ModelDraft:
        ticket = request.ticket
        category = self._classify(
            ticket.subject + " " + ticket.description,
            ticket.current_category,
        )
        priority = self._priority(
            category,
            ticket.current_priority,
            ticket.customer_tier,
        )
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
            citation_indexes=list(range(1, len(hits) + 1)),
        )

    def decision(
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

    def reply(
        self,
        draft: ModelDraft,
        hits: list[RetrievalHit],
        evidence_missing: bool,
    ) -> SuggestedReply:
        citation_hits = self._citation_hits(draft.citation_indexes, hits)
        citations = [citation_label(hit) for hit in citation_hits]
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

    def _citation_hits(
        self,
        citation_indexes: list[int],
        hits: list[RetrievalHit],
    ) -> list[RetrievalHit]:
        if not hits:
            if citation_indexes:
                raise InvalidModelResponseError
            return []
        if not citation_indexes or len(set(citation_indexes)) != len(citation_indexes):
            raise InvalidModelResponseError
        if any(index < 1 or index > len(hits) for index in citation_indexes):
            raise InvalidModelResponseError
        return [hits[index - 1] for index in citation_indexes]

    def workflow_steps(
        self,
        observation: WorkflowObservation,
    ) -> list[WorkflowStep]:
        return [
            WorkflowStep(
                id="normalize",
                name="内容预处理",
                description="语言识别与输入校验完成",
                status="complete",
                duration_ms=12,
            ),
            WorkflowStep(
                id="classify",
                name="工单理解",
                description="类别、优先级与情绪识别完成",
                status="complete",
                duration_ms=max(18, observation.generation_ms // 3),
            ),
            WorkflowStep(
                id="retrieve",
                name="知识检索",
                description=(
                    "未找到满足阈值的有效证据"
                    if observation.evidence_missing
                    else f"最终采用 {observation.hit_count} 条知识片段"
                ),
                status="complete",
                duration_ms=max(0, observation.retrieval_ms),
            ),
            WorkflowStep(
                id="generate",
                name="回复生成",
                description=(
                    "实时调用失败，已生成本地谨慎回复"
                    if observation.failed_live
                    else "已根据证据生成回复草稿"
                ),
                status="failed" if observation.failed_live else "complete",
                duration_ms=max(0, observation.generation_ms),
            ),
            WorkflowStep(
                id="risk",
                name="风险检查",
                description=(
                    "证据不足，转入人工复核"
                    if observation.evidence_missing
                    else "确定性风险规则检查完成"
                ),
                status="complete",
                duration_ms=8,
            ),
        ]

    def _classify(self, text: str, current_category: str) -> str:
        lowered = text.lower()
        rules = [
            ("BILLING", ("重复扣款", "重复支付", "两笔扣款", "账单")),
            ("ACCOUNT_ACCESS", ("sso", "登录", "账号锁定")),
            ("INVOICE", ("发票", "抬头")),
            ("PRIVACY", ("数据删除", "离职员工", "隐私", "授权材料")),
            ("DATA_EXPORT", ("导出", "处理中", "exp-")),
            ("SUBSCRIPTION", ("专业版", "套餐", "协作者", "成员上限")),
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
