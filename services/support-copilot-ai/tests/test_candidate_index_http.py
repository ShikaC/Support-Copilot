"""Actual Node generation followed by SDK embedding of that selected corpus."""

import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

import pytest

from tests.test_index_rebuild_http_support import (
    embedding_server,
    record_http_response,
    running_api,
    seeded_index,
    terminal_response,
)


@pytest.mark.parametrize("failure", [False, True])
def test_generated_corpus_to_index_http_preserves_active_and_source_identity(
    tmp_path: Path,
    record_property: Callable[[str, str], None],
    failure: bool,
) -> None:
    source = tmp_path / "documents.json"
    source.write_text(
        json.dumps(
            {
                "doc_data": {
                    "dmv": {
                        "sample": {
                            "doc_id": "sample",
                            "title": "Candidate",
                            "doc_text": "A😀BCDE",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with embedding_server(failure=failure) as provider:
        fixture = seeded_index(tmp_path, provider)
        with running_api(fixture, provider, corpus_enabled=True) as client:
            generated = client.post(
                "/knowledge/corpus/build",
                json={
                    "expectedSourceChecksum": sha256(source.read_bytes()).hexdigest(),
                    "window": 4,
                    "stride": 3,
                },
            )
            assert generated.status_code == 202
            corpus_response = terminal_response(client, generated.headers["Location"])
            corpus = corpus_response.json()
            assert corpus["status"] == "SUCCEEDED"
            record_property("corpus", corpus_response.text)
            request = {
                "corpusBuildTaskId": corpus["taskId"],
                "expectedCorpusChecksum": corpus["result"]["corpusChecksum"],
                "maxEmbeddingCalls": 1,
            }
            accepted = client.post("/knowledge/index/rebuild", json=request)
            assert accepted.status_code == 202, accepted.text
            record_http_response(record_property, "accepted", accepted)
            assert provider.entered.wait(5)
            assert provider.calls[0].input == ["A😀BC", "CDE"]
            assert client.get("/health/live").status_code == 200
            provider.release.set()
            response = terminal_response(client, accepted.headers["Location"])
            status = response.json()
            record_http_response(record_property, "terminal", response)
            assert status["corpusBuildTaskId"] == corpus["taskId"]
            assert status["corpusChecksum"] == corpus["result"]["corpusChecksum"]
            assert status["embeddingCalls"] == len(provider.calls) == 1
            if failure:
                assert status["status"] == "FAILED"
                assert status["failureCode"] == "EMBEDDING_PROVIDER_FAILED"
            else:
                assert status["status"] == "SUCCEEDED"
                manifest = json.loads(
                    (fixture.root / status["artifactId"] / "manifest.json").read_bytes()
                )
                assert manifest["corpus_checksum"] == corpus["result"]["corpusChecksum"]
                assert manifest["chunking_version"] == "doc2dial-codepoints-4-3-v1"
                reused = client.post("/knowledge/index/rebuild", json=request)
                assert reused.status_code == 202
                reused_status = terminal_response(
                    client, reused.headers["Location"]
                ).json()
                assert reused_status["artifactId"] == status["artifactId"]
                assert reused_status["embeddingCalls"] == 0
            assert fixture.corpus.read_bytes() == fixture.corpus_bytes
            assert (fixture.root / "active.json").read_bytes() == fixture.pointer_bytes
        with running_api(fixture, provider, enabled=False) as client:
            restarted = client.get(accepted.headers["Location"])
            assert restarted.json() == status
            assert len(provider.calls) == 1
            record_http_response(record_property, "restarted", restarted)
