from typing import Literal


ExternalAiOperation = Literal["embedding", "structured_generation"]
ExternalAiFailureKind = Literal[
    "api_error",
    "connection_timeout",
    "response_timeout",
    "invalid_response",
]


class RecoverableAiError(Exception):
    def __init__(
        self,
        operation: ExternalAiOperation,
        failure_kind: ExternalAiFailureKind,
    ) -> None:
        self.operation = operation
        self.failure_kind = failure_kind
        super().__init__(f"External AI {operation} failed ({failure_kind})")


class ExternalAiServiceError(RecoverableAiError):
    pass


class EmbeddingApiError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(operation="embedding", failure_kind="api_error")


class EmbeddingConnectionTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(operation="embedding", failure_kind="connection_timeout")


class EmbeddingResponseTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(operation="embedding", failure_kind="response_timeout")


class StructuredGenerationApiError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(operation="structured_generation", failure_kind="api_error")


class StructuredGenerationConnectionTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="structured_generation",
            failure_kind="connection_timeout",
        )


class StructuredGenerationResponseTimeoutError(ExternalAiServiceError):
    def __init__(self) -> None:
        super().__init__(
            operation="structured_generation",
            failure_kind="response_timeout",
        )


class InvalidModelResponseError(RecoverableAiError):
    def __init__(self) -> None:
        super().__init__(
            operation="structured_generation",
            failure_kind="invalid_response",
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
