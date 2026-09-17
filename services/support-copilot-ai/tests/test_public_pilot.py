import json

import httpx
import pytest

from evaluation.public_pilot_data import (
    PublicCase,
    Question,
    Source,
    bm25_scores,
    citations_in_bounds,
    split_document,
)
from evaluation.public_pilot_trial import TrialInput, pilot_access, run_trial
from tests.test_openai_provider_protocols import (
    DRAFT_PAYLOAD,
    _chat_payload,
    _settings,
    _wire_provider,
)


def test_chunk_source_lines_reconstruct_original_document() -> None:
    # Given a document long enough to need several windows.
    text = "\n".join(f"original line {index}" for index in range(65))
    # When extracting chunks.
    chunks = split_document("gh_auth_login", text)
    # Then every cited source range resolves to the original text.
    assert len(chunks) >= 3
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 65
    assert all(chunk.content == "\n".join(text.splitlines()[chunk.start_line - 1:chunk.end_line]) for chunk in chunks)


def test_bm25_prioritizes_relevant_content_not_empty_matches() -> None:
    # Given unrelated authentication and download documents.
    chunks = split_document("gh_auth_login", "login token authentication") + split_document("gh_release_download", "resume download file")
    # When asking about authentication.
    scores = bm25_scores(chunks, "authentication token")
    # Then only the relevant document receives a positive score.
    assert scores[0] > scores[1] == 0.0


def test_invalid_and_duplicate_citations_are_not_accepted() -> None:
    # Given two evidence pieces and several malformed citation lists.
    invalid = [[0], [-1], [3], [1, 1]]
    # When checking the model's indexes.
    accepted = [citations_in_bounds(indexes, 2) for indexes in invalid]
    # Then neither out-of-range nor duplicate references are accepted.
    assert accepted == [False] * 4


def test_empty_citations_can_represent_an_abstention() -> None:
    # Given an empty evidence context.
    # When validating no citations.
    valid = citations_in_bounds([], 0)
    # Then structural validity does not require hallucinating an index.
    assert valid


def trial_input() -> TrialInput:
    case = PublicCase(id="public-test", source=Source(url="https://github.com/cli/cli/issues/375", title="Login"),
        input=Question(question="How can I authenticate?", language="en"))
    return TrialInput(case, "bm25", split_document("gh_auth_login", "Use token authentication."), [1.0], 0.0)


@pytest.mark.anyio
async def test_trial_preserves_invalid_citation_output_without_marking_it_correct() -> None:
    # Given a successful real SDK parse with an out-of-range model citation.
    payload = {**DRAFT_PAYLOAD, "citation_indexes": [2]}

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_payload(content=json.dumps(payload)))

    provider, client = _wire_provider(_settings("chat_completions"), respond)
    # When the experiment records this single attempt.
    async with client:
        result = await run_trial(provider, trial_input(), pilot_access("a" * 64))
    # Then the invalid output remains inspectable and never becomes a quality success.
    assert result.status == "INVALID_CITATIONS"
    assert result.draft is not None and result.draft.citation_indexes == [2]
    assert result.answer_correct is None and result.human_review == "NOT_REVIEWED"


@pytest.mark.anyio
async def test_trial_records_http_failure_once_without_exposing_response_secrets() -> None:
    # Given an unavailable provider whose error body contains sensitive text.
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(503, json={"error": {"message": "PRIVATE_SENTINEL", "type": "server_error"}})

    provider, client = _wire_provider(_settings("chat_completions"), respond)
    # When recording an external dependency failure.
    async with client:
        result = await run_trial(provider, trial_input(), pilot_access("a" * 64))
    # Then failure is retained without retry, fabricated usage or sensitive diagnostics.
    assert result.status == "PROVIDER_ERROR" and len(calls) == 1
    assert result.draft is None and result.input_tokens is None
    assert result.diagnostics is not None and result.diagnostics["http_status"] == 503
    assert "PRIVATE_SENTINEL" not in result.model_dump_json()
