from enum import StrEnum
from typing import Literal


ExternalAiOperation = Literal["embedding", "structured_generation"]
ExternalAiFailureKind = Literal[
    "api_error",
    "connection_timeout",
    "response_timeout",
    "invalid_response",
]


class FallbackReason(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    EMBEDDING_API_ERROR = "embedding_api_error"
    EMBEDDING_CONNECTION_TIMEOUT = "embedding_connection_timeout"
    EMBEDDING_RESPONSE_TIMEOUT = "embedding_response_timeout"
    STRUCTURED_GENERATION_API_ERROR = "structured_generation_api_error"
    STRUCTURED_GENERATION_CONNECTION_TIMEOUT = (
        "structured_generation_connection_timeout"
    )
    STRUCTURED_GENERATION_RESPONSE_TIMEOUT = "structured_generation_response_timeout"
    INVALID_MODEL_RESPONSE = "invalid_model_response"
    PROCESSING_TIMEOUT = "processing_timeout"
    AI_SERVICE_TIMEOUT = "ai_service_timeout"
    AI_SERVICE_UNAVAILABLE = "ai_service_unavailable"
    AI_SERVICE_ERROR = "ai_service_error"
    INVALID_AI_RESPONSE = "invalid_ai_response"


class LiveProviderConfigurationError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Live mode is not configured")


class RecoverableAiError(Exception):
    def __init__(
        self,
        operation: ExternalAiOperation,
        failure_kind: ExternalAiFailureKind,
        fallback_reason: FallbackReason,
    ) -> None:
        self.operation = operation
        self.failure_kind = failure_kind
        self.fallback_reason = fallback_reason
        super().__init__(f"External AI {operation} failed ({failure_kind})")


class ExternalAiServiceError(RecoverableAiError):
    pass


class EmbeddingApiError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="embedding",
            failure_kind="api_error",
            fallback_reason=FallbackReason.EMBEDDING_API_ERROR,
        )


class EmbeddingConnectionTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="embedding",
            failure_kind="connection_timeout",
            fallback_reason=FallbackReason.EMBEDDING_CONNECTION_TIMEOUT,
        )


class EmbeddingResponseTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="embedding",
            failure_kind="response_timeout",
            fallback_reason=FallbackReason.EMBEDDING_RESPONSE_TIMEOUT,
        )


class StructuredGenerationApiError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="structured_generation",
            failure_kind="api_error",
            fallback_reason=FallbackReason.STRUCTURED_GENERATION_API_ERROR,
        )


class StructuredGenerationConnectionTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="structured_generation",
            failure_kind="connection_timeout",
            fallback_reason=FallbackReason.STRUCTURED_GENERATION_CONNECTION_TIMEOUT,
        )


class StructuredGenerationResponseTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="structured_generation",
            failure_kind="response_timeout",
            fallback_reason=FallbackReason.STRUCTURED_GENERATION_RESPONSE_TIMEOUT,
        )


class InvalidModelResponseError(RecoverableAiError):
    def __init__(self) -> None:
        super().__init__(
            operation="structured_generation",
            failure_kind="invalid_response",
            fallback_reason=FallbackReason.INVALID_MODEL_RESPONSE,
        )


def timeout_failure_kind(error: BaseException) -> ExternalAiFailureKind:
    cause = error.__cause__
    if cause is not None and type(cause).__name__ == "ConnectTimeout":
        return "connection_timeout"
    return "response_timeout"


def embedding_timeout_error(error: BaseException) -> ExternalAiServiceError:
    if timeout_failure_kind(error) == "connection_timeout":
        return EmbeddingConnectionTimeoutError()
    return EmbeddingResponseTimeoutError()


def structured_generation_timeout_error(
    error: BaseException,
) -> ExternalAiServiceError:
    if timeout_failure_kind(error) == "connection_timeout":
        return StructuredGenerationConnectionTimeoutError()
    return StructuredGenerationResponseTimeoutError()
