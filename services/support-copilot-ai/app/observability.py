import logging
from typing import Final


STRUCTURED_LOG_FORMAT: Final = (
    "%(asctime)s %(levelname)s %(name)s event=%(message)s "
    "trace_id=%(trace_id)s timeout_seconds=%(timeout_seconds)s "
    "error_code=%(error_code)s error_type=%(error_type)s "
    "mode=%(mode)s status=%(status)s hit_count=%(hit_count)s reason=%(reason)s "
    "protocol=%(protocol)s model_response_failure_kind=%(model_response_failure_kind)s"
)


class StructuredLogDefaults(logging.Filter):
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
