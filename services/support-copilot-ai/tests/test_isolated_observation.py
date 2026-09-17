import json
from pathlib import Path

import httpx
import pytest
from app.errors import InvalidModelResponseError, ModelResponseFailureKind
from evaluation.isolated_observation import (
    AttemptLedger,
    BenchmarkBudgetExceeded,
    trace,
)
from openai import RateLimitError


def events(file: Path) -> list[dict[str, str | int | None]]:
    return [json.loads(line) for line in file.read_text().splitlines()]


def test_started_is_durable_before_operation_and_success_retains_trace(tmp_path: Path) -> None:
    file = tmp_path / "attempts.jsonl"
    ledger = AttemptLedger(file, 2)
    token = trace.set("trace_test")
    try:
        with ledger.attempt("generation"):
            assert events(file)[0]["phase"] == "STARTED"
    finally:
        trace.reset(token)
    rows = events(file)
    assert [row["phase"] for row in rows] == ["STARTED", "SUCCEEDED"]
    assert rows[0]["attempt_id"] == rows[1]["attempt_id"]
    assert rows[0]["trace_id"] == "trace_test"
    assert rows[1]["input_tokens"] is None


def test_budget_is_enforced_before_next_operation(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 1)
    with ledger.attempt("generation"):
        pass
    with pytest.raises(BenchmarkBudgetExceeded), ledger.attempt("generation"):
        pytest.fail("Must not start an over-budget operation")
    assert len(events(ledger.file)) == 2


def test_unknown_error_is_recorded_reraised_and_blocks_further_calls(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 2)
    with pytest.raises(RuntimeError, match="private error"), ledger.attempt("generation"):
        raise RuntimeError("private error")
    assert "private error" not in ledger.file.read_text()
    assert events(ledger.file)[-1]["phase"] == "FAILED"
    with pytest.raises(BenchmarkBudgetExceeded), ledger.attempt("query_embedding"):
        pytest.fail("Unknown errors must stop further paid work")


def test_quota_error_latches_both_operation_budgets(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 2)
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.invalid"))
    with pytest.raises(RateLimitError), ledger.attempt("generation"):
        raise RateLimitError("private provider error", response=response, body=None)
    assert events(ledger.file)[-1]["http_status"] == 429
    assert ledger.blocked
    assert "private provider error" not in ledger.file.read_text()


def test_interruption_preserves_unknown_in_flight(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 1)
    with pytest.raises(KeyboardInterrupt), ledger.attempt("generation"):
        raise KeyboardInterrupt
    assert events(ledger.file)[-1]["phase"] == "UNKNOWN_INTERRUPTED"


def test_completion_fsync_failure_blocks_next_paid_operation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 2)
    calls = 0

    def fail_completion(_fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated disk failure")

    monkeypatch.setattr("evaluation.isolated_observation.os.fsync", fail_completion)
    with pytest.raises(OSError), ledger.attempt("generation"):
        pass
    with pytest.raises(BenchmarkBudgetExceeded), ledger.attempt("query_embedding"):
        pytest.fail("Java retry must not cause another paid call")


def test_retrieval_write_failure_blocks_next_paid_operation(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 2)
    with ledger.attempt("query_embedding"):
        pass
    with pytest.raises(OSError):
        ledger.persist_retrieval(tmp_path / "missing" / "hits.jsonl", "[]")
    with pytest.raises(BenchmarkBudgetExceeded), ledger.attempt("query_embedding"):
        pytest.fail("Retry must be stopped after losing retrieval evidence")


def test_post_provider_program_error_latches_the_whole_workflow(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 2)
    with pytest.raises(RuntimeError), ledger.failure_boundary():
        with ledger.attempt("query_embedding"):
            pass
        raise RuntimeError("downstream scoring or serialization failure")
    with pytest.raises(BenchmarkBudgetExceeded), ledger.attempt("query_embedding"):
        pytest.fail("Retry after successful provider + failed workflow must not pay again")


def test_modeled_invalid_response_preserves_fallback_and_allows_next_case(tmp_path: Path) -> None:
    ledger = AttemptLedger(tmp_path / "attempts.jsonl", 2)
    with pytest.raises(InvalidModelResponseError), ledger.attempt("generation"):
        raise InvalidModelResponseError(ModelResponseFailureKind.PARSED_NONE)
    row = events(ledger.file)[-1]
    assert row["application_failure_kind"] == "invalid_response"
    assert row["model_response_failure_kind"] == "parsed_none"
    assert row["unknown_error"] is False
    assert not ledger.blocked
    with ledger.attempt("query_embedding"):
        pass
