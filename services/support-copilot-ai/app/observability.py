import logging
from typing import Final

import httpx
from openai import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
)
from typing_extensions import override

STRUCTURED_LOG_FORMAT: Final = (
    "%(asctime)s %(levelname)s %(name)s event=%(message)s "
    "trace_id=%(trace_id)s timeout_seconds=%(timeout_seconds)s "
    "error_code=%(error_code)s error_type=%(error_type)s "
    "mode=%(mode)s status=%(status)s hit_count=%(hit_count)s reason=%(reason)s "
    "protocol=%(protocol)s model_response_failure_kind=%(model_response_failure_kind)s "
    "sdk_error_kind=%(sdk_error_kind)s transport_cause_kind=%(transport_cause_kind)s "
    "http_status=%(http_status)s"
)


class StructuredLogDefaults(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        defaults: dict[str, str] = {
            "trace_id": "none",
            "timeout_seconds": "none",
            "error_code": "none",
            "error_type": "none",
            "mode": "none",
            "status": "none",
            "hit_count": "none",
            "reason": "none",
            "protocol": "none",
            "model_response_failure_kind": "none",
            "sdk_error_kind": "none",
            "transport_cause_kind": "none",
            "http_status": "none",
        }
        for name, value in defaults.items():
            if not hasattr(record, name):
                setattr(record, name, value)
        return True


def configure_structured_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=STRUCTURED_LOG_FORMAT)
    for handler in logging.getLogger().handlers:
        if not any(
            isinstance(log_filter, StructuredLogDefaults)
            for log_filter in handler.filters
        ):
            handler.addFilter(StructuredLogDefaults())
        handler.setFormatter(logging.Formatter(STRUCTURED_LOG_FORMAT))


_SDK_FAILURE_KINDS: Final[tuple[tuple[type[BaseException], str], ...]] = (
    (APITimeoutError, "APITimeoutError"),
    (APIConnectionError, "APIConnectionError"),
    (APIStatusError, "APIStatusError"),
    (APIResponseValidationError, "APIResponseValidationError"),
    (APIError, "APIError"),
)
_TRANSPORT_FAILURE_KINDS: Final[tuple[tuple[type[BaseException], str], ...]] = (
    (httpx.ConnectTimeout, "ConnectTimeout"),
    (httpx.ReadTimeout, "ReadTimeout"),
    (httpx.WriteTimeout, "WriteTimeout"),
    (httpx.PoolTimeout, "PoolTimeout"),
    (httpx.ConnectError, "ConnectError"),
    (httpx.ReadError, "ReadError"),
    (httpx.WriteError, "WriteError"),
    (httpx.CloseError, "CloseError"),
    (httpx.RemoteProtocolError, "RemoteProtocolError"),
    (httpx.LocalProtocolError, "LocalProtocolError"),
    (httpx.ProxyError, "ProxyError"),
    (httpx.TimeoutException, "TimeoutException"),
    (httpx.TransportError, "TransportError"),
)


def safe_provider_failure_details(error: BaseException) -> dict[str, str | int]:
    """Classify a bounded explicit cause chain without serializing exception content."""
    details: dict[str, str | int] = {
        "sdk_error_kind": "none", "transport_cause_kind": "none", "http_status": "none",
    }
    current: BaseException | None = error
    seen: set[int] = set()
    for _ in range(12):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        for field, kinds in (
            ("sdk_error_kind", _SDK_FAILURE_KINDS),
            ("transport_cause_kind", _TRANSPORT_FAILURE_KINDS),
        ):
            if details[field] == "none":
                details[field] = next((name for kind, name in kinds if isinstance(current, kind)), "none")
        if isinstance(current, APIStatusError) and details["http_status"] == "none" and 100 <= current.status_code <= 599:
            details["http_status"] = current.status_code
        current = current.__cause__
    return details
