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

    # Then: Java owns service retries, so the provider SDK makes one attempt.
    assert settings.openai_timeout_seconds == 20
    assert settings.openai_max_retries == 0
    assert settings.ai_processing_timeout_seconds == 90


def test_chat_protocol_defaults_to_responses() -> None:
    assert Settings(_env_file=None).openai_chat_protocol == "responses"


def test_chat_completions_protocol_parses_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_CHAT_PROTOCOL", "chat_completions")

    assert Settings(_env_file=None).openai_chat_protocol == "chat_completions"


def test_unknown_chat_protocol_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(openai_chat_protocol="automatic", _env_file=None)


def test_rejects_unbounded_openai_retry_configuration() -> None:
    # Given: live requests are configured with more retries than the V1.5 budget allows.
    # When/Then: settings reject the unsafe retry count at the environment boundary.
    with pytest.raises(ValidationError, match="OPENAI_MAX_RETRIES"):
        Settings(openai_max_retries=2, _env_file=None)


def test_bounded_legacy_retry_setting_remains_parseable() -> None:
    settings = Settings(openai_max_retries=1, _env_file=None)

    assert settings.openai_max_retries == 1


def test_retrieval_score_defaults_are_explicit_and_bounded() -> None:
    # Given: the repository's default retrieval safety configuration.
    settings = Settings(_env_file=None)

    # Then: mock and live thresholds use their documented score domains.
    assert settings.mock_retrieval_min_score == 0.25
    assert settings.live_retrieval_min_score == 0.35


def test_embedding_base_url_can_differ_from_chat_base_url() -> None:
    # Given: chat and embedding providers are configured at different endpoints.
    settings = Settings(
        openai_base_url="https://chat.example.test/v1",
        openai_embedding_base_url="https://embedding.example.test/v1",
        _env_file=None,
    )

    # Then: each client receives its own endpoint and the embedding endpoint wins.
    assert settings.openai_base_url == "https://chat.example.test/v1"
    assert settings.embedding_base_url == "https://embedding.example.test/v1"


def test_embedding_base_url_defaults_to_chat_base_url() -> None:
    # Given: only the existing compatible gateway setting is configured.
    settings = Settings(
        openai_base_url="https://gateway.example.test/v1",
        _env_file=None,
    )

    # Then: existing single-gateway configurations keep working for embeddings.
    assert settings.embedding_base_url == "https://gateway.example.test/v1"


def test_embedding_api_key_defaults_to_chat_api_key() -> None:
    # Given: one provider key is shared by chat and embeddings.
    settings = Settings(
        openai_api_key="shared-provider-key",
        _env_file=None,
    )

    # Then: the embedding client falls back to the shared key.
    assert settings.embedding_api_key == "shared-provider-key"


def test_dedicated_embedding_api_key_overrides_chat_api_key() -> None:
    # Given: chat and embedding providers require different credentials.
    settings = Settings(
        openai_api_key="chat-provider-key",
        openai_embedding_api_key="embedding-provider-key",
        _env_file=None,
    )

    # Then: the embedding client receives only its dedicated credential.
    assert settings.embedding_api_key == "embedding-provider-key"


def test_embedding_base_url_reads_dedicated_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the dedicated embedding endpoint is supplied at the environment boundary.
    monkeypatch.setenv(
        "OPENAI_EMBEDDING_BASE_URL",
        "https://embedding.example.test/v1",
    )

    # When: settings parse the environment variables.
    settings = Settings(_env_file=None)

    # Then: the dedicated endpoint is available to the embedding client.
    assert settings.embedding_base_url == "https://embedding.example.test/v1"


def test_rejects_live_retrieval_score_outside_cosine_domain() -> None:
    # Given: a threshold outside the cosine similarity range.
    # When/Then: settings reject it before the live service starts.
    with pytest.raises(ValidationError):
        Settings(live_retrieval_min_score=1.1, _env_file=None)
