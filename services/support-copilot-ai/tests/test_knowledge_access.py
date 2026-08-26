import logging
from pathlib import Path
from types import SimpleNamespace

from _pytest.logging import LogCaptureFixture
import pytest

from app.analysis_runner import AnalysisRunner
from app.config import Settings
from app.knowledge import (
    KnowledgeReleaseMismatchError,
    KnowledgeRetriever,
    RetrievalRequest,
)
from app.models import (
    AnalyzeRequest,
    KnowledgeAccess,
    ModelDraft,
    Priority,
    Sentiment,
    SupportScope,
    TicketInput,
)
from app.workflow import AnalysisWorkflow
from tests.knowledge_access_support import CapturingEmbeddings, write_canary_corpus


class SyntheticProgrammingError(RuntimeError):
    pass


@pytest.mark.asyncio
async def test_retriever_rejects_release_mismatch_before_retrieval(
    tmp_path: Path,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    checksum = write_canary_corpus(knowledge_path)
    retriever = KnowledgeRetriever(
        Settings(ai_mode="mock", knowledge_path=knowledge_path)
    )
    request = RetrievalRequest(
        ticket=TicketInput(
            id="ticket-release-mismatch",
            subject="Duplicate charge",
            description="COLLIDING_CANARY",
            currentCategory="BILLING",
        ),
        query="COLLIDING_CANARY duplicate charge",
        top_n=10,
        top_k=3,
        live=False,
        knowledge_access=KnowledgeAccess(
            releaseId="support-kb-test",
            releaseVersion=2,
            corpusChecksum=checksum,
            allowedScopes=["BILLING"],
        ),
    )

    with pytest.raises(KnowledgeReleaseMismatchError) as error:
        await retriever.search(request)

    assert error.value.code == "KNOWLEDGE_RELEASE_MISMATCH"


@pytest.mark.asyncio
async def test_local_workflow_filters_forbidden_chunks_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    checksum = write_canary_corpus(knowledge_path)
    settings = Settings(ai_mode="mock", knowledge_path=knowledge_path)
    retriever = KnowledgeRetriever(settings)
    observed_chunk_ids: list[str] = []
    original_score = retriever._local_candidate_score

    def observe_score(chunk, query: str) -> float:
        observed_chunk_ids.append(chunk.chunk_id)
        return original_score(chunk, query)

    monkeypatch.setattr(retriever, "_local_candidate_score", observe_score)
    runner = AnalysisRunner(settings, AnalysisWorkflow(settings, retriever))
    request = AnalyzeRequest(
        traceId="trace_local_scope",
        ticket=TicketInput(
            id="ticket-local-scope",
            subject="Duplicate charge",
            description="COLLIDING_CANARY duplicate charge investigation",
            currentCategory="BILLING",
        ),
        knowledgeAccess=KnowledgeAccess(
            releaseId="support-kb-test",
            releaseVersion=1,
            corpusChecksum=checksum,
            allowedScopes=["BILLING"],
        ),
    )
    caplog.set_level(logging.INFO)

    response = await runner.run(request)
    serialized = response.model_dump_json()

    assert observed_chunk_ids == ["billing-canary"]
    assert [hit.chunk_id for hit in response.retrieval.hits] == ["billing-canary"]
    assert "FORBIDDEN_CANARY" not in serialized
    assert "privacy-forbidden-canary" not in serialized
    assert "FORBIDDEN_CANARY" not in caplog.text
    assert "privacy-forbidden-canary" not in caplog.text


def _live_settings(knowledge_path: Path) -> Settings:
    return Settings(
        ai_mode="live",
        knowledge_path=knowledge_path,
        openai_api_key="synthetic-test-key",
        openai_chat_model="synthetic-chat-model",
        openai_embedding_model="synthetic-embedding-model",
        embedding_artifact_root=knowledge_path.parent / "embedding-artifacts",
        embedding_vector_dimension=2,
        embedding_artifact_build_policy="build-if-missing",
    )


@pytest.mark.asyncio
async def test_live_workflow_never_sends_forbidden_chunks_to_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    checksum = write_canary_corpus(knowledge_path)
    embeddings = CapturingEmbeddings()
    monkeypatch.setattr(
        "app.embedding_provider.OpenAIEmbeddings",
        lambda **_kwargs: embeddings,
    )
    settings = _live_settings(knowledge_path)
    retriever = KnowledgeRetriever(settings)
    scored_rows: list[tuple[int, ...]] = []
    original_score_rows = retriever._live_index._score_rows

    def observe_score_rows(matrix, query, rows):
        scored_rows.append(rows)
        return original_score_rows(matrix, query, rows)

    monkeypatch.setattr(retriever._live_index, "_score_rows", observe_score_rows)
    workflow = AnalysisWorkflow(settings, retriever)
    model_inputs: list[str] = []

    async def parse(**kwargs):
        model_inputs.append(kwargs["input"])
        return SimpleNamespace(
            output_parsed=ModelDraft(
                intent="billing_investigation",
                category="BILLING",
                priority=Priority.HIGH,
                sentiment=Sentiment.NEGATIVE,
                confidence=0.9,
                reason_summary="Authorized billing evidence matched.",
                reply_content="We will investigate the duplicate charge.",
                warnings=[],
                citation_indexes=[1],
            ),
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )

    assert workflow._provider is not None
    workflow._provider._client = SimpleNamespace(
        responses=SimpleNamespace(parse=parse)
    )
    runner = AnalysisRunner(settings, workflow)
    request = AnalyzeRequest(
        traceId="trace_live_scope",
        ticket=TicketInput(
            id="ticket-live-scope",
            subject="Duplicate charge",
            description="COLLIDING_CANARY duplicate charge investigation",
            currentCategory="BILLING",
        ),
        knowledgeAccess=KnowledgeAccess(
            releaseId="support-kb-test",
            releaseVersion=1,
            corpusChecksum=checksum,
            allowedScopes=["BILLING"],
        ),
    )
    caplog.set_level(logging.INFO)

    response = await runner.run(request)
    observable = "\n".join(
        [
            *embeddings.queries,
            *model_inputs,
            response.model_dump_json(),
            caplog.text,
        ]
    )

    assert len(embeddings.documents) == 2
    assert scored_rows == [(0,)]
    assert "support-kb-test" in model_inputs[0]
    assert "BILLING" in model_inputs[0]
    assert "FORBIDDEN_CANARY" not in observable
    assert "privacy-forbidden-canary" not in observable


@pytest.mark.asyncio
async def test_empty_scopes_skip_embedding_and_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    checksum = write_canary_corpus(knowledge_path)

    def reject_embedding(**_kwargs):
        raise AssertionError("embedding provider must not be constructed")

    monkeypatch.setattr("app.embedding_provider.OpenAIEmbeddings", reject_embedding)
    settings = _live_settings(knowledge_path)
    workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))

    async def reject_generation(*_args, **_kwargs):
        raise AssertionError("generation provider must not receive evidence")

    assert workflow._provider is not None
    monkeypatch.setattr(workflow._provider, "analyze", reject_generation)
    runner = AnalysisRunner(settings, workflow)
    request = AnalyzeRequest(
        traceId="trace_empty_scope",
        ticket=TicketInput(
            id="ticket-empty-scope",
            subject="Duplicate charge",
            description="COLLIDING_CANARY duplicate charge investigation",
            currentCategory="BILLING",
        ),
        knowledgeAccess=KnowledgeAccess(
            releaseId="support-kb-test",
            releaseVersion=1,
            corpusChecksum=checksum,
            allowedScopes=[],
        ),
    )

    response = await runner.run(request)

    assert response.status == "FALLBACK"
    assert response.retrieval.hits == []
    assert response.suggested_reply.citations == []


@pytest.mark.asyncio
async def test_programming_errors_are_not_converted_to_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    checksum = write_canary_corpus(knowledge_path)
    settings = Settings(ai_mode="mock", knowledge_path=knowledge_path)
    retriever = KnowledgeRetriever(settings)

    def fail_scoring(_chunk, _query: str) -> float:
        raise SyntheticProgrammingError("synthetic programming defect")

    monkeypatch.setattr(retriever, "_local_candidate_score", fail_scoring)
    request = AnalyzeRequest(
        traceId="trace_programming_error",
        ticket=TicketInput(
            id="ticket-programming-error",
            subject="Duplicate charge",
            description="COLLIDING_CANARY",
            currentCategory="BILLING",
        ),
        knowledgeAccess=KnowledgeAccess(
            releaseId="support-kb-test",
            releaseVersion=1,
            corpusChecksum=checksum,
            allowedScopes=["BILLING"],
        ),
    )

    with pytest.raises(RuntimeError, match="synthetic programming defect"):
        await AnalysisRunner(
            settings,
            AnalysisWorkflow(settings, retriever),
        ).run(request)
