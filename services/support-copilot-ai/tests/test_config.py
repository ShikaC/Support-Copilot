import pytest

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
