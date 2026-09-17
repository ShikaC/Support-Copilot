import io
import logging

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app import observability

SECRET = "PRIVATE_BODY_TOKEN_DO_NOT_LOG"


def _request() -> httpx.Request:
    return httpx.Request("POST", f"https://private.invalid/{SECRET}",
                         headers={"authorization": f"Bearer {SECRET}"}, content=SECRET)


@pytest.mark.parametrize("status", [429, 503])
def test_status_failure_diagnostics_keep_only_status_and_fixed_kind(status: int) -> None:
    # Given a wrapped SDK failure with secret URL, headers, body and message.
    error = APIStatusError(SECRET, response=httpx.Response(status, request=_request()), body={"secret": SECRET})
    wrapper = RuntimeError(SECRET)
    wrapper.__cause__ = error
    # When safe diagnostic fields are extracted.
    details = observability.safe_provider_failure_details(wrapper)
    # Then only whitelisted classification and status are present.
    assert details == {"sdk_error_kind": "APIStatusError", "transport_cause_kind": "none", "http_status": status}


@pytest.mark.parametrize("transport,kind", [
    (httpx.ConnectError, "ConnectError"),
    (httpx.ConnectTimeout, "ConnectTimeout"),
    (httpx.ReadTimeout, "ReadTimeout"),
    (httpx.WriteTimeout, "WriteTimeout"),
    (httpx.PoolTimeout, "PoolTimeout"),
])
def test_connection_diagnostics_walk_explicit_causes_without_reading_messages(
    transport: type[httpx.TransportError], kind: str,
) -> None:
    # Given a wrapped SDK connection failure whose transport cause has secrets.
    error = APIConnectionError(message=SECRET, request=_request())
    error.__cause__ = transport(SECRET)
    wrapper = RuntimeError(SECRET)
    wrapper.__cause__ = error
    # When classifying its cause chain.
    details = observability.safe_provider_failure_details(wrapper)
    # Then fixed transport category distinguishes the network failure.
    assert details == {"sdk_error_kind": "APIConnectionError", "transport_cause_kind": kind, "http_status": "none"}


def test_sdk_timeout_is_distinguished_from_generic_connection_error() -> None:
    # Given APITimeoutError is also a subclass of APIConnectionError.
    error = APITimeoutError(request=_request())
    # When classifying the error itself.
    details = observability.safe_provider_failure_details(error)
    # Then the more specific fixed SDK category wins.
    assert details["sdk_error_kind"] == "APITimeoutError"


def test_unknown_error_without_cause_has_only_none_defaults() -> None:
    # Given an unrelated error whose text must never enter provider logs.
    error = RuntimeError(SECRET)
    # When extracting provider diagnostics.
    details = observability.safe_provider_failure_details(error)
    # Then unknown classes and text are not serialized.
    assert details == {"sdk_error_kind": "none", "transport_cause_kind": "none", "http_status": "none"}


def test_cyclic_cause_chain_terminates() -> None:
    # Given a malformed explicit cause cycle.
    error = RuntimeError(SECRET)
    error.__cause__ = error
    # When extracting bounded diagnostic information.
    details = observability.safe_provider_failure_details(error)
    # Then cycles terminate with safe defaults.
    assert details["sdk_error_kind"] == "none"


def test_shared_formatter_renders_safe_fields_and_no_sensitive_exception_data() -> None:
    # Given a real SDK failure and the actual shared structured formatter.
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(observability.StructuredLogDefaults())
    handler.setFormatter(logging.Formatter(observability.STRUCTURED_LOG_FORMAT))
    error = APIStatusError(SECRET, response=httpx.Response(503, request=_request()), body=SECRET)
    fields = observability.safe_provider_failure_details(error)
    # When emitting diagnostics without exc_info or raw exception interpolation.
    record = logging.LogRecord("provider-test", logging.WARNING, "fixture", 1, "analysis.external_failure", (), None)
    for key, value in fields.items():
        setattr(record, key, value)
    _ = handler.handle(record)
    # Then status/kind are useful and no request or response material is exposed.
    output = stream.getvalue()
    assert "sdk_error_kind=APIStatusError" in output
    assert "transport_cause_kind=none" in output
    assert "http_status=503" in output
    assert SECRET not in output
    assert "private.invalid" not in output
    assert "authorization" not in output
