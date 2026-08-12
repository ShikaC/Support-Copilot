from openai import AsyncOpenAI, OpenAIError

from app.config import Settings
from app.errors import ExternalAiServiceError, InvalidModelResponseError
from app.models import ModelDraft, PromptVersion, RetrievalHit, TicketInput
from app.prompts import instructions_for


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    async def analyze(
        self,
        ticket: TicketInput,
        evidence: list[RetrievalHit],
        prompt_version: PromptVersion,
    ) -> tuple[ModelDraft, int, int]:
        evidence_text = "\n\n".join(
            f"[{index}] {hit.document_title} {hit.section}\n{hit.content}"
            for index, hit in enumerate(evidence, start=1)
        )
        try:
            response = await self._client.responses.parse(
                model=self._settings.openai_chat_model,
                instructions=instructions_for(prompt_version),
                input=(
                    f"工单标题：{ticket.subject}\n"
                    f"工单正文：{ticket.description}\n"
                    f"客户等级：{ticket.customer_tier}\n"
                    f"当前分类：{ticket.current_category}\n"
                    f"当前优先级：{ticket.current_priority}\n\n"
                    f"知识片段：\n{evidence_text or '没有检索到有效知识片段'}"
                ),
                text_format=ModelDraft,
            )
        except OpenAIError as exc:
            # 只有 OpenAI SDK 明确报告的外部故障才允许进入工作流 fallback。
            raise ExternalAiServiceError(operation="structured analysis") from exc

        if response.output_parsed is None:
            raise InvalidModelResponseError

        usage = response.usage
        return (
            response.output_parsed,
            usage.input_tokens if usage else 0,
            usage.output_tokens if usage else 0,
        )
