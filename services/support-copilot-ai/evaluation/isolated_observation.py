"""Durable provider-operation accounting for the isolated benchmark only."""
import os
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import ClassVar, Literal
from uuid import uuid4

from app.errors import RecoverableAiError
from app.observability import safe_provider_failure_details
from pydantic import BaseModel, ConfigDict

trace: ContextVar[str] = ContextVar("benchmark_trace", default="none")


class AttemptEvent(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    attempt_id: str
    trace_id: str
    operation: Literal["query_embedding", "generation"]
    phase: Literal["STARTED", "SUCCEEDED", "FAILED", "UNKNOWN_INTERRUPTED"]
    at: datetime
    elapsed_ms: float | None = None
    sdk_error_kind: str | int | None = None
    transport_cause_kind: str | int | None = None
    http_status: str | int | None = None
    application_failure_kind: str | None = None
    model_response_failure_kind: str | None = None
    unknown_error: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None


class BenchmarkBudgetExceeded(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Isolated benchmark provider budget exhausted")


class AttemptLedger:
    def __init__(self, file: Path, limit: int) -> None:
        self.file: Path = file
        self.limit: int = limit
        self.counts: dict[str, int] = {"query_embedding": 0, "generation": 0}
        self.blocked: bool = False

    def append(self, event: AttemptEvent) -> None:
        try:
            with self.file.open("a", encoding="utf-8") as stream:
                _ = stream.write(event.model_dump_json() + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            self.blocked = True
            raise

    def persist_retrieval(self, file: Path, payload: str) -> None:
        try:
            with file.open("a", encoding="utf-8") as stream:
                _ = stream.write(payload + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            self.blocked = True
            raise

    @contextmanager
    def failure_boundary(self) -> Generator[None]:
        try:
            yield
        except Exception:  # Observer boundary latches failures; HTTP still receives the original error.
            self.blocked = True
            raise

    @contextmanager
    def attempt(self, operation: Literal["query_embedding", "generation"]) -> Generator[None]:
        if self.blocked or self.counts[operation] >= self.limit or sum(self.counts.values()) >= self.limit * 2:
            raise BenchmarkBudgetExceeded
        self.counts[operation] += 1
        event = AttemptEvent(attempt_id=uuid4().hex, trace_id=trace.get(), operation=operation,
                             phase="STARTED", at=datetime.now(UTC))
        self.append(event)
        started = perf_counter()
        phase: Literal["SUCCEEDED", "FAILED", "UNKNOWN_INTERRUPTED"] = "UNKNOWN_INTERRUPTED"
        details: dict[str, str | int | bool | None] = {}
        try:
            yield
            phase = "SUCCEEDED"
        except Exception as exc:  # Sole observer boundary: record, then re-raise unchanged.
            phase = "FAILED"
            details.update(safe_provider_failure_details(exc))
            known = isinstance(exc, RecoverableAiError)
            details["application_failure_kind"] = exc.failure_kind if known else None
            details["model_response_failure_kind"] = exc.model_response_failure_kind if known else None
            details["unknown_error"] = not known and details["sdk_error_kind"] == "none"
            if details["http_status"] in (401, 403, 429) or details["unknown_error"]:
                self.blocked = True
            raise
        finally:
            if phase == "UNKNOWN_INTERRUPTED":
                self.blocked = True
            self.append(event.model_copy(update={"phase": phase, "at": datetime.now(UTC),
                "elapsed_ms": (perf_counter()-started)*1000, **details}))
