from app.models import ModelDraft


def is_english(language: str) -> bool:
    return language.lower().split("-")[0] == "en"


def insufficient_draft(draft: ModelDraft, language: str) -> ModelDraft:
    english = is_english(language)
    return draft.model_copy(
        update={
            "evidence_sufficient": False,
            "citation_indexes": [],
            "confidence": min(draft.confidence, 0.42),
            "reply_content": (
                "I do not have sufficient verified evidence to answer this request. "
                + "A support specialist needs to review it before any action or commitment."
                if english
                else "当前没有足够的有效知识支持这一请求，需要由支持人员进一步核实。"
                + "在完成核实前，暂时无法确认处理方式或承诺结果。"
            ),
            "warnings": [
                "Insufficient evidence; human review is required."
                if english
                else "证据不足，必须人工复核，禁止承诺处理结果。"
            ],
        }
    )
