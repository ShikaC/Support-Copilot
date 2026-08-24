from typing import Final

from app.config import Settings

COLD_LIVE_EXTERNAL_REQUESTS: Final = 3
PYTHON_OVERHEAD_SECONDS: Final = 5
UPSTREAM_MARGIN_SECONDS: Final = 10


class UnsafeTimeoutBudgetError(Exception):
    def __init__(self, layer: str, requirement: str) -> None:
        self.layer = layer
        self.requirement = requirement
        super().__init__(f"Unsafe {layer} timeout budget: {requirement}")


def validate_timeout_budget(
    settings: Settings,
    java_timeout_ms: int,
    client_timeout_seconds: int,
) -> None:
    external_attempt_seconds = settings.openai_timeout_seconds * (
        settings.openai_max_retries + 1
    )
    cold_live_seconds = (
        settings.openai_timeout_seconds * COLD_LIVE_EXTERNAL_REQUESTS
    )
    minimum_processing_seconds = (
        max(external_attempt_seconds, cold_live_seconds) + PYTHON_OVERHEAD_SECONDS
    )
    if settings.ai_processing_timeout_seconds <= minimum_processing_seconds:
        raise UnsafeTimeoutBudgetError(
            layer="Python",
            requirement=(
                "AI_PROCESSING_TIMEOUT_SECONDS must exceed the cold live request "
                f"budget ({minimum_processing_seconds:g}s)"
            ),
        )

    java_timeout_seconds = java_timeout_ms / 1_000
    minimum_java_seconds = (
        settings.ai_processing_timeout_seconds + UPSTREAM_MARGIN_SECONDS
    )
    if java_timeout_seconds <= minimum_java_seconds:
        raise UnsafeTimeoutBudgetError(
            layer="Java",
            requirement=(
                "AI_SERVICE_TIMEOUT_MS must exceed the Python deadline plus margin "
                f"({minimum_java_seconds:g}s)"
            ),
        )

    minimum_client_seconds = java_timeout_seconds + UPSTREAM_MARGIN_SECONDS
    if client_timeout_seconds <= minimum_client_seconds:
        raise UnsafeTimeoutBudgetError(
            layer="client",
            requirement=(
                "SUPPORT_COPILOT_HTTP_TIMEOUT_SECONDS must exceed the Java deadline "
                f"plus margin ({minimum_client_seconds:g}s)"
            ),
        )
