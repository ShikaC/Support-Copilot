import pytest
from pydantic import ValidationError

from app.config import Settings


def test_empty_provenance_environment_value_uses_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the optional provenance variable is present but empty.
    monkeypatch.setenv("KNOWLEDGE_PROVENANCE_PATH", "")

    # When: settings parse the environment template value.
    settings = Settings(_env_file=None)

    # Then: the service keeps provenance optional instead of treating '.' as a file.
    assert settings.knowledge_provenance_path is None


def test_default_live_timeouts_have_a_bounded_retry_budget() -> None:
    # Given: no local .env overrides the repository defaults.
    # When: the service settings are loaded.
    settings = Settings(_env_file=None)

    # Then: one external retry fits inside a larger whole-analysis deadline.
    assert settings.openai_timeout_seconds == 20
    assert settings.openai_max_retries == 1
    assert settings.ai_processing_timeout_seconds == 90


def test_rejects_unbounded_openai_retry_configuration() -> None:
    # Given: live requests are configured with more retries than the V1.5 budget allows.
    # When/Then: settings reject the unsafe retry count at the environment boundary.
    with pytest.raises(ValidationError, match="OPENAI_MAX_RETRIES"):
        Settings(openai_max_retries=2, _env_file=None)
