import json
from pathlib import Path
from types import SimpleNamespace

import anyio
import numpy as np
import pytest

from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge_source import KnowledgeChunk, load_knowledge_corpus
from app.live_vector_index import LiveVectorIndex, RetrievalWindow
from app.models import (
    AnalyzeOptions,
    AnalyzeRequest,
    KnowledgeAccess,
    SupportScope,
    TicketInput,
)
from app.workflow import AnalysisWorkflow
from evaluation import retrieval_only
from tests.knowledge_access_support import write_test_corpus

QUERY_VECTOR = [1.0, 0.0, 0.0]
# 顺序必须与 CHUNKS 一致；E 与 query 完全同向，但 scope 不允许，用于检验过滤是否生效。
DOCUMENT_VECTORS = [
    [1.0, 0.0, 0.0],
    [0.9, 0.43589, 0.0],
    [0.1, 0.99499, 0.0],
    [0.8, 0.6, 0.0],
    [1.0, 0.0, 0.0],
]


def make_chunk(
    chunk_id: str,
    categories: list[str],
    scopes: list[str],
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        document_title=f"Title {chunk_id}",
        section=f"Section {chunk_id}",
        content=f"content {chunk_id}",
        source_uri=f"kb://{chunk_id}/v1",
        categories=categories,
        keywords=[chunk_id],
        allowed_scopes=scopes,
        document_version="v1",
        status="PUBLISHED",
        updated_at="2026-09-17",
    )


CHUNKS = (
    make_chunk("chunk-a", ["BILLING"], ["GENERAL"]),
    make_chunk("chunk-b", ["GENERAL"], ["GENERAL"]),
    make_chunk("chunk-c", ["GENERAL"], ["GENERAL"]),
    make_chunk("chunk-d", ["BILLING"], ["GENERAL"]),
    make_chunk("chunk-e", ["GENERAL"], ["PRIVACY"]),
)


class StubProvider:
    """确定性的向量来源：文档向量按 corpus 顺序给出，query 向量固定。"""

    def __init__(self, documents: list[list[float]], query: list[float]) -> None:
        self._documents = documents
        self._query = query
        self.query_calls = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == len(self._documents)
        return self._documents

    async def embed_query(self, _text: str) -> list[float]:
        self.query_calls += 1
        return self._query


def build_test_settings(corpus_path: Path, artifact_root: Path) -> Settings:
    return Settings(
        ai_mode="mock",
        knowledge_path=corpus_path,
        embedding_artifact_root=artifact_root,
        openai_embedding_model="fake-model",
        embedding_vector_dimension=3,
        embedding_chunking_version="knowledge-corpus-v2",
        live_retrieval_min_score=0.35,
        _env_file=None,
    )


@pytest.fixture
def harness(tmp_path: Path) -> SimpleNamespace:
    corpus_path = tmp_path / "corpus.json"
    write_test_corpus(corpus_path, CHUNKS)
    settings = build_test_settings(corpus_path, tmp_path / "artifacts")
    corpus = load_knowledge_corpus(corpus_path)
    provider = StubProvider(DOCUMENT_VECTORS, QUERY_VECTOR)
    store = EmbeddingArtifactStore(settings, corpus)
    manifest = anyio.run(store.build, provider)
    store.activate(manifest.artifact_id)
    return SimpleNamespace(
        tmp_path=tmp_path,
        corpus_path=corpus_path,
        settings=settings,
        corpus=corpus,
        provider=provider,
        store=store,
        artifact=store.load_active(),
        ticket=TicketInput(
            id="ticket-1",
            subject="Subject line",
            description="user: hello\nagent: hi",
            current_category="GENERAL",
        ),
    )


def script_ranking(
    harness: SimpleNamespace,
    query: str,
    *,
    category: str,
    top_n: int = 10,
    top_k: int = 3,
) -> list[tuple[str, float]]:
    rows = retrieval_only.eligible_rows(harness.corpus, retrieval_only.ALLOWED_SCOPES)
    scored = retrieval_only.cosine_scores(
        harness.artifact.matrix,
        np.asarray(QUERY_VECTOR, dtype=np.float32),
        rows,
    )
    ranked = retrieval_only.rank_candidates(
        scored,
        harness.corpus,
        category,
        min_score=harness.settings.live_retrieval_min_score,
        top_n=top_n,
        top_k=top_k,
    )
    return [(harness.corpus.chunks[row].chunk_id, round(score, 4)) for row, score in ranked]


def index_ranking(
    harness: SimpleNamespace,
    query: str,
    *,
    top_n: int = 10,
    top_k: int = 3,
) -> list[tuple[str, float]]:
    index = LiveVectorIndex(harness.settings, harness.corpus)
    index._provider = harness.provider
    index._artifact = harness.artifact
    hits = anyio.run(
        index.search,
        harness.ticket,
        query,
        RetrievalWindow(top_n, top_k),
        retrieval_only.ALLOWED_SCOPES,
    )
    return [(hit.chunk_id, hit.initial_score) for hit in hits]


def test_build_query_matches_workflow() -> None:
    subject = "Public support request"
    description = "user: hello\nagent: hi"
    request = AnalyzeRequest(
        trace_id="trace_0123456789abcdefghij",
        ticket=TicketInput(id="ticket-1", subject=subject, description=description),
        knowledge_access=KnowledgeAccess(
            release_id="support-kb-test",
            release_version=1,
            corpus_checksum="a" * 64,
            allowed_scopes=(SupportScope.GENERAL,),
        ),
        options=AnalyzeOptions(),
    )
    assert retrieval_only.build_query(subject, description) == AnalysisWorkflow._build_query(
        None, request
    )


def test_eligible_rows_match_index_scope_filtering(harness: SimpleNamespace) -> None:
    index = LiveVectorIndex(harness.settings, harness.corpus)
    expected = index._eligible_rows(retrieval_only.ALLOWED_SCOPES)
    assert retrieval_only.eligible_rows(harness.corpus, retrieval_only.ALLOWED_SCOPES) == expected
    # PRIVACY 片段必须被排除，否则范围过滤形同虚设。
    assert len(expected) == 4


def test_script_ranking_equals_index_search(harness: SimpleNamespace) -> None:
    query = retrieval_only.build_query(harness.ticket.subject, harness.ticket.description)
    expected = index_ranking(harness, query)
    assert script_ranking(harness, query, category="GENERAL") == expected
    # 类别重排必须生效：初排第一的 chunk-a 属于 BILLING，工单类别是 GENERAL。
    assert [chunk_id for chunk_id, _ in expected] == ["chunk-b", "chunk-a", "chunk-d"]


def test_unclassified_ticket_category_degrades_to_score_order(harness: SimpleNamespace) -> None:
    # TicketService 新建工单的类别是 UNCLASSIFIED，真实语料的 chunk categories 全是 GENERAL，
    # 因此类别重排不改变顺序，结果必须与纯分数排序一致。
    query = "category degradation probe"
    assert script_ranking(harness, query, category="UNCLASSIFIED") == [
        ("chunk-a", 1.0),
        ("chunk-b", 0.9),
        ("chunk-d", 0.8),
    ]


def test_threshold_and_top_n_limits_are_applied(harness: SimpleNamespace) -> None:
    query = "low similarity probe"
    # chunk-c 的余弦为 0.1，低于 0.35 阈值，必须被丢弃。
    assert script_ranking(harness, query, category="GENERAL", top_n=2, top_k=3) == [
        ("chunk-b", 0.9),
        ("chunk-a", 1.0),
    ]
    assert script_ranking(harness, query, category="GENERAL", top_n=10, top_k=1) == [("chunk-b", 0.9)]


def test_prepare_run_writes_plan_without_calling_provider(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        retrieval_only, "Settings", lambda **kwargs: build_test_settings(harness.corpus_path, harness.tmp_path / "artifacts")
    )
    (harness.tmp_path / "inputs.json").write_text(
        json.dumps([{"id": "case-1", "input": {"subject": "S", "description": "D"}}]),
        encoding="utf-8",
    )
    args = retrieval_only.parse_args(
        [
            "--root", str(harness.tmp_path),
            "--inputs", "inputs.json",
            "--corpus", "corpus.json",
            "--artifact-root", "artifacts",
            "--output", "out",
        ]
    )
    assert anyio.run(retrieval_only.run, args) == 0
    plan = json.loads((harness.tmp_path / "out" / "retrieval-plan.json").read_text(encoding="utf-8"))
    assert plan["mode"] == "retrieval-only"
    assert plan["plannedEmbeddingCalls"] == 1
    assert plan["plannedGenerationCalls"] == 0
    assert harness.provider.query_calls == 0
    assert not (harness.tmp_path / "out" / "results.json").exists()


def test_execute_run_writes_results_vectors_and_manifest(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        retrieval_only, "Settings", lambda **kwargs: build_test_settings(harness.corpus_path, harness.tmp_path / "artifacts")
    )
    monkeypatch.setattr(
        retrieval_only, "OpenAIEmbeddingProvider", lambda settings: harness.provider
    )
    (harness.tmp_path / "inputs.json").write_text(
        json.dumps(
            [
                {"id": "case-1", "input": {"subject": "S", "description": "D"}},
                {"id": "case-2", "input": {"subject": "S", "description": "D"}},
            ]
        ),
        encoding="utf-8",
    )
    args = retrieval_only.parse_args(
        [
            "--root", str(harness.tmp_path),
            "--inputs", "inputs.json",
            "--corpus", "corpus.json",
            "--artifact-root", "artifacts",
            "--output", "out",
            "--category", "GENERAL",
            "--execute",
        ]
    )
    assert anyio.run(retrieval_only.run, args) == 0

    results = json.loads((harness.tmp_path / "out" / "results.json").read_text(encoding="utf-8"))
    assert [record["caseId"] for record in results] == ["case-1", "case-2"]
    body = results[0]["stages"]["analyze"]["body"]
    assert body["mode"] == "retrieval-only"
    assert [hit["chunk_id"] for hit in body["retrieval"]["hits"]] == [
        "chunk-b",
        "chunk-a",
        "chunk-d",
    ]
    # 检索-only 运行必须留下可解释的调用计数：只有 embedding，没有生成。
    manifest = json.loads(
        (harness.tmp_path / "out" / "retrieval-only-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["executedEmbeddingCalls"] == 2
    assert manifest["executedGenerationCalls"] == 0
    assert manifest["casesWithHits"] == 2
    vectors = json.loads((harness.tmp_path / "out" / "query-vectors.json").read_text(encoding="utf-8"))
    assert len(vectors["case-1"]) == 3


def test_execute_refuses_to_overwrite_mismatched_plan(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        retrieval_only, "Settings", lambda **kwargs: build_test_settings(harness.corpus_path, harness.tmp_path / "artifacts")
    )
    monkeypatch.setattr(
        retrieval_only, "OpenAIEmbeddingProvider", lambda settings: harness.provider
    )
    inputs_file = harness.tmp_path / "inputs.json"
    inputs_file.write_text(
        json.dumps([{"id": "case-1", "input": {"subject": "S", "description": "D"}}]),
        encoding="utf-8",
    )
    out_dir = harness.tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "retrieval-plan.json").write_text(
        json.dumps({"querySha256": "stale-plan"}), encoding="utf-8"
    )
    args = retrieval_only.parse_args(
        [
            "--root", str(harness.tmp_path),
            "--inputs", "inputs.json",
            "--corpus", "corpus.json",
            "--artifact-root", "artifacts",
            "--output", "out",
            "--execute",
        ]
    )
    with pytest.raises(ValueError, match="不要覆盖既有证据"):
        anyio.run(retrieval_only.run, args)
    assert harness.provider.query_calls == 0


@pytest.mark.parametrize("existing", ["results.json", "query-vectors.json", "retrieval-only-manifest.json", "execution-claim.json"])
def test_execute_rejects_existing_execution_before_provider_call(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, existing: str,
) -> None:
    # Given: even a partial previous execution is retained as evidence.
    monkeypatch.setattr(retrieval_only, "Settings", lambda **kwargs: harness.settings)
    monkeypatch.setattr(retrieval_only, "OpenAIEmbeddingProvider", lambda _: harness.provider)
    (harness.tmp_path / "inputs.json").write_text(json.dumps([
        {"id": "case-1", "input": {"subject": "S", "description": "D"}},
    ]))
    output = harness.tmp_path / "out"
    output.mkdir()
    (output / existing).write_text("{}")
    args = retrieval_only.parse_args([
        "--root", str(harness.tmp_path), "--inputs", "inputs.json",
        "--corpus", "corpus.json", "--artifact-root", "artifacts",
        "--output", "out", "--execute",
    ])
    # When: the same output directory is accidentally executed again.
    with pytest.raises(FileExistsError):
        anyio.run(retrieval_only.run, args)
    # Then: no billable work happens before the refusal.
    assert harness.provider.query_calls == 0


def test_failed_execution_retains_claim_and_refuses_retry(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the external dependency fails on the first attempt.
    monkeypatch.setattr(retrieval_only, "Settings", lambda **kwargs: harness.settings)
    class FailingProvider:
        calls = 0

        async def embed_query(self, _text: str) -> list[float]:
            self.calls += 1
            raise RuntimeError("simulated external interruption")

    provider = FailingProvider()
    monkeypatch.setattr(retrieval_only, "OpenAIEmbeddingProvider", lambda _: provider)
    (harness.tmp_path / "inputs.json").write_text(json.dumps([
        {"id": "case-1", "input": {"subject": "S", "description": "D"}},
    ]))
    args = retrieval_only.parse_args([
        "--root", str(harness.tmp_path), "--inputs", "inputs.json",
        "--corpus", "corpus.json", "--artifact-root", "artifacts",
        "--output", "out", "--execute",
    ])
    with pytest.raises(RuntimeError):
        anyio.run(retrieval_only.run, args)
    # When: retrying that failed execution.
    with pytest.raises(FileExistsError):
        anyio.run(retrieval_only.run, args)
    # Then: the initial attempt remains the only external call.
    assert provider.calls == 1


@pytest.mark.parametrize("field,value", [
    ("artifactId", "0" * 64),
    ("embeddingModel", "different-model"),
    ("corpusSha256", "0" * 64),
    ("topK", 1),
])
def test_execute_rejects_prepared_plan_drift_before_provider_call(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, field: str, value: str | int,
) -> None:
    monkeypatch.setattr(retrieval_only, "Settings", lambda **kwargs: harness.settings)
    monkeypatch.setattr(retrieval_only, "OpenAIEmbeddingProvider", lambda _: harness.provider)
    (harness.tmp_path / "inputs.json").write_text(json.dumps([
        {"id": "case-1", "input": {"subject": "S", "description": "D"}},
    ]))
    args = retrieval_only.parse_args([
        "--root", str(harness.tmp_path), "--inputs", "inputs.json",
        "--corpus", "corpus.json", "--artifact-root", "artifacts", "--output", "out",
    ])
    anyio.run(retrieval_only.run, args)
    plan_file = harness.tmp_path / "out/retrieval-plan.json"
    plan = json.loads(plan_file.read_text())
    plan[field] = value
    plan_file.write_text(json.dumps(plan))
    args.execute = True
    with pytest.raises(ValueError, match="不要覆盖既有证据"):
        anyio.run(retrieval_only.run, args)
    assert harness.provider.query_calls == 0


def test_concurrent_execution_claim_allows_only_one_embedding_call(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retrieval_only, "Settings", lambda **kwargs: harness.settings)
    (harness.tmp_path / "inputs.json").write_text(json.dumps([
        {"id": "case-1", "input": {"subject": "S", "description": "D"}},
    ]))
    args = retrieval_only.parse_args([
        "--root", str(harness.tmp_path), "--inputs", "inputs.json",
        "--corpus", "corpus.json", "--artifact-root", "artifacts", "--output", "out", "--execute",
    ])

    async def scenario() -> None:
        entered = anyio.Event()
        release = anyio.Event()

        class BlockingProvider:
            calls = 0

            async def embed_query(self, _text: str) -> list[float]:
                self.calls += 1
                entered.set()
                await release.wait()
                return QUERY_VECTOR

        provider = BlockingProvider()
        monkeypatch.setattr(retrieval_only, "OpenAIEmbeddingProvider", lambda _: provider)
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(retrieval_only.run, args)
            await entered.wait()
            try:
                with pytest.raises(FileExistsError):
                    await retrieval_only.run(args)
            finally:
                release.set()
        assert provider.calls == 1

    anyio.run(scenario)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_execute_rejects_nonfinite_query_vector_without_recording_no_evidence(
    harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, value: float,
) -> None:
    monkeypatch.setattr(retrieval_only, "Settings", lambda **kwargs: harness.settings)
    harness.provider._query = [value, 0.0, 0.0]
    monkeypatch.setattr(retrieval_only, "OpenAIEmbeddingProvider", lambda _: harness.provider)
    (harness.tmp_path / "inputs.json").write_text(json.dumps([
        {"id": "case-1", "input": {"subject": "S", "description": "D"}},
    ]))
    args = retrieval_only.parse_args([
        "--root", str(harness.tmp_path), "--inputs", "inputs.json",
        "--corpus", "corpus.json", "--artifact-root", "artifacts",
        "--output", "out", "--execute",
    ])
    with pytest.raises(ValueError, match="非有限值"):
        anyio.run(retrieval_only.run, args)
    assert harness.provider.query_calls == 1
    assert (harness.tmp_path / "out/execution-claim.json").exists()
    assert not (harness.tmp_path / "out/results.json").exists()
    assert not (harness.tmp_path / "out/query-vectors.json").exists()
