from typing import assert_never

from openai import APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.config import Settings
from app.data_redaction import redact_sensitive_text
from app.errors import (
    InvalidModelResponseError,
    ModelResponseFailureKind,
    StructuredGenerationApiError,
    structured_generation_timeout_error,
)
from app.models import AnalyzeRequest, ModelDraft, RetrievalHit
from app.prompts import instructions_for


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            # Java owns bounded service retries. Keep the SDK at one attempt so
            # an old validated OPENAI_MAX_RETRIES=1 setting cannot multiply them.
            max_retries=0,
        )

    async def analyze(
        self,
        request: AnalyzeRequest,
        evidence: list[RetrievalHit],
    ) -> tuple[ModelDraft, int, int]:
        ticket = request.ticket
        access = request.knowledge_access
        evidence_text = "\n\n".join(
            f"[{index}] {hit.document_title} {hit.section}\n{hit.content}"
            for index, hit in enumerate(evidence, start=1)
        )
        model_input = redact_sensitive_text(
            f"工单标题：{ticket.subject}\n"
            f"工单正文：{ticket.description}\n"
            f"客户等级：{ticket.customer_tier}\n"
            f"当前分类：{ticket.current_category}\n"
            f"当前优先级：{ticket.current_priority}\n\n"
            f"知识发布：{access.release_id} v{access.release_version}\n"
            f"授权范围：{','.join(access.allowed_scopes)}\n\n"
            f"知识片段：\n{evidence_text or '没有检索到有效知识片段'}"
        )
        try:
            match self._settings.openai_chat_protocol:
                case "responses":
                    response = await self._client.responses.parse(
                        model=self._settings.openai_chat_model,
                        instructions=instructions_for(request.options.prompt_version),
                        input=model_input,
                        store=False,
                        text_format=ModelDraft,
                    )
                    parsed = response.output_parsed
                    usage = response.usage
                    input_tokens = usage.input_tokens if usage else 0
                    output_tokens = usage.output_tokens if usage else 0
                case "chat_completions":
                    completion = await self._client.chat.completions.parse(
                        model=self._settings.openai_chat_model,
                        messages=[
                            {
                                "role": "system",
                                "content": instructions_for(request.options.prompt_version),
                            },
                            {"role": "user", "content": model_input},
                        ],
                        response_format=ModelDraft,
                        store=False,
                    )
                    if not completion.choices:
                        raise InvalidModelResponseError(
                            ModelResponseFailureKind.NO_CHOICE,
                        )
                    message = completion.choices[0].message
                    if message.refusal is not None:
                        raise InvalidModelResponseError(
                            ModelResponseFailureKind.REFUSAL,
                        )
                    parsed = message.parsed
                    usage = completion.usage
                    input_tokens = usage.prompt_tokens if usage else 0
                    output_tokens = usage.completion_tokens if usage else 0
                case unreachable:
                    assert_never(unreachable)

            if parsed is None:
                raise InvalidModelResponseError(ModelResponseFailureKind.PARSED_NONE)
            draft = ModelDraft.model_validate(parsed)
        except APITimeoutError as exc:
            raise structured_generation_timeout_error(exc) from exc
        except OpenAIError as exc:
            # 只有 OpenAI SDK 明确报告的外部故障才允许进入工作流 fallback。
            raise StructuredGenerationApiError from exc
        except ValidationError as exc:
            raise InvalidModelResponseError(
                ModelResponseFailureKind.SCHEMA_VALIDATION,
            ) from exc

        return draft, input_tokens, output_tokens
