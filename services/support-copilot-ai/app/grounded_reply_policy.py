import hashlib
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.models import AnalyzeRequest, ModelDraft, Priority, RetrievalHit
from app.response_language import insufficient_draft, is_english


class ResponsePolicy(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    id: str
    category: str
    chunk_id: str
    source_sha256: str
    required_topics: tuple[str, ...]
    reply_zh: str
    reply_en: str


class PolicyCatalog(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    version: str
    policies: tuple[ResponsePolicy, ...]


class GroundedReplyPolicy:
    def __init__(self) -> None:
        path = Path(__file__).parent / "data" / "response_policies.json"
        self._catalog: PolicyCatalog = PolicyCatalog.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def apply(
        self,
        request: AnalyzeRequest,
        draft: ModelDraft,
        hits: list[RetrievalHit],
    ) -> ModelDraft:
        if not draft.evidence_sufficient:
            return insufficient_draft(draft, request.ticket.language)
        topic = f"{request.ticket.subject}\n{request.ticket.description}".casefold()
        english = is_english(request.ticket.language)
        paragraphs: list[str] = []
        citation_indexes: list[int] = []
        for policy in self._catalog.policies:
            if policy.category != draft.category:
                continue
            if policy.required_topics and not any(term.casefold() in topic for term in policy.required_topics):
                continue
            for index, hit in enumerate(hits, start=1):
                if hit.chunk_id != policy.chunk_id:
                    continue
                if (
                    hashlib.sha256(hit.content.encode("utf-8")).hexdigest()
                    != policy.source_sha256
                ):
                    return insufficient_draft(draft, request.ticket.language)
                paragraphs.append(policy.reply_en if english else policy.reply_zh)
                citation_indexes.append(index)
                break
        if not paragraphs:
            return draft
        warning = (
            f"Reply constrained by source-bound policy {self._catalog.version}; human review required."
            if english
            else f"回复已由来源绑定规则 {self._catalog.version} 约束，仍需人工审核。"
        )
        priority = draft.priority
        if draft.category in {"BILLING", "PRIVACY"} and priority in {
            Priority.LOW,
            Priority.MEDIUM,
        }:
            priority = Priority.HIGH
        return draft.model_copy(
            update={
                "reply_content": "\n\n".join(paragraphs),
                "citation_indexes": citation_indexes,
                "warnings": list(dict.fromkeys([*draft.warnings, warning])),
                "priority": priority,
            }
        )
