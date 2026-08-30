import pytest

from app.errors import (
    EmbeddingApiError,
    EmbeddingConnectionTimeoutError,
    EmbeddingResponseTimeoutError,
    InvalidModelResponseError,
    ModelResponseFailureKind,
    RecoverableAiError,
    StructuredGenerationApiError,
    StructuredGenerationConnectionTimeoutError,
    StructuredGenerationResponseTimeoutError,
)


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (EmbeddingApiError(), "embedding_api_error"),
        (EmbeddingConnectionTimeoutError(), "embedding_connection_timeout"),
        (EmbeddingResponseTimeoutError(), "embedding_response_timeout"),
        (StructuredGenerationApiError(), "structured_generation_api_error"),
        (
            StructuredGenerationConnectionTimeoutError(),
            "structured_generation_connection_timeout",
        ),
        (
            StructuredGenerationResponseTimeoutError(),
            "structured_generation_response_timeout",
        ),
        (
            InvalidModelResponseError(ModelResponseFailureKind.SCHEMA_VALIDATION),
            "invalid_model_response",
        ),
    ],
)
def test_recoverable_ai_error_has_stable_fallback_reason(
    error: RecoverableAiError,
    expected_reason: str,
) -> None:
    # Given: each named external AI failure crosses the workflow boundary.
    # When: the workflow reads its machine-consumable fallback reason.
    actual_reason = error.fallback_reason

    # Then: the reason identifies the failed operation and failure kind.
    assert actual_reason == expected_reason
