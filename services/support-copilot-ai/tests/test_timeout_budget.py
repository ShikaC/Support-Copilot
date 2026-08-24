import pytest

from app.config import Settings
from app.timeout_budget import UnsafeTimeoutBudgetError, validate_timeout_budget


def test_default_cross_service_timeout_budget_is_ordered() -> None:
    # Given: the documented Python, Java, and live-client defaults.
    settings = Settings(_env_file=None)

    # When/Then: every caller stops later than the layer it is waiting for.
    validate_timeout_budget(settings, java_timeout_ms=105_000, client_timeout_seconds=120)


def test_rejects_java_timeout_shorter_than_python_processing_budget() -> None:
    # Given: Java would stop while Python could still consume its live budget.
    settings = Settings(_env_file=None)

    # When/Then: live preflight rejects the inverted deadline order.
    with pytest.raises(UnsafeTimeoutBudgetError, match="Java"):
        validate_timeout_budget(settings, java_timeout_ms=80_000, client_timeout_seconds=120)


def test_rejects_live_client_timeout_shorter_than_java_budget() -> None:
    # Given: the verification client would disconnect before Java finishes.
    settings = Settings(_env_file=None)

    # When/Then: live preflight rejects the ineffective client deadline.
    with pytest.raises(UnsafeTimeoutBudgetError, match="client"):
        validate_timeout_budget(settings, java_timeout_ms=105_000, client_timeout_seconds=100)
