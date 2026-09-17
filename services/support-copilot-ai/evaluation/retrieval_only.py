"""检索-only 离线评测：只调用 embedding，不调用生成模型。

为什么需要它：真实召回无法从既有运行记录判断——旧运行的 13 题共用了同一条 query，
候选集完全相同，gold 命中为 0 既不能证明检索坏，也不能证明已修好。而 chat 端点不可用时
无法重跑整批生成；检索只依赖 embedding 与已构建的向量 artifact，可以单独执行，
把结果写成运行记录格式后交给 `scripts/benchmark/retrieval-eval.mjs` 统一评分。

纪律：本脚本不修改任何生产检索代码，只按同一顺序复现 `LiveVectorIndex.search`
的判定；`tests/test_retrieval_only.py` 用同一份输入断言两条路径给出完全相同的候选与分数。

用法：

    # 1. 只做装配检查与计划，不产生任何外部调用
    python -m evaluation.retrieval_only --output docs/verification/retrieval-only-2026-09-17

    # 2. 真实执行（每题一次 embedding 调用，无生成调用）
    python -m evaluation.retrieval_only --output docs/verification/retrieval-only-2026-09-17 --execute
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
import numpy as np

from app.config import Settings
from app.data_redaction import redact_sensitive_text
from app.embedding_artifact import EmbeddingArtifactStore
from app.embedding_provider import EmbeddingProvider, OpenAIEmbeddingProvider
from app.knowledge_source import KnowledgeCorpus, load_knowledge_corpus
from app.models import RetrievalHit, SupportScope

DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUTS = "docs/verification/quality-input-audit-2026-09-10/inputs-development.json"
DEFAULT_CORPUS = "docs/verification/business-benchmark-2026-09-10/corpus.json"
DEFAULT_ARTIFACT_ROOT = ".local/business-benchmark-runtime/artifacts"
# 该 artifact 由隔离运行器用这组显式配置构建；不显式覆盖就会因 chunking_version
# 与默认值不同而报 artifact-incompatible。
DEFAULT_CHUNKING_VERSION = "doc2dial-codepoints-2000-1600-v1"
DEFAULT_TOP_N = 10
DEFAULT_TOP_K = 3
# TicketService 新建工单时写入 UNCLASSIFIED；真实语料的 chunk categories 全是 GENERAL，
# 因此类别重排在真实数据上等价于按分数排序。这里显式记录，便于对照。
DEFAULT_CATEGORY = "UNCLASSIFIED"
ALLOWED_SCOPES: tuple[SupportScope, ...] = (SupportScope.GENERAL,)
MODE = "retrieval-only"


def build_query(subject: str, description: str) -> str:
    """与 AnalysisWorkflow._build_query 保持同一构造方式：subject 加 description。"""
    return f"{subject} {description}".strip()


def eligible_rows(
    corpus: KnowledgeCorpus,
    allowed_scopes: tuple[SupportScope, ...] = ALLOWED_SCOPES,
) -> tuple[int, ...]:
    """与 LiveVectorIndex._eligible_rows 一致：按允许范围筛选可打分行。"""
    scope_set = frozenset(allowed_scopes)
    return tuple(
        row
        for row, chunk in enumerate(corpus.chunks)
        if scope_set.intersection(chunk.allowed_scopes)
    )


def cosine_scores(
    matrix: np.ndarray,
    query: np.ndarray,
    rows: tuple[int, ...],
) -> list[tuple[int, float]]:
    """与 LiveVectorIndex._score_rows 一致的余弦相似度，零范数记 0。"""
    eligible = matrix[np.asarray(rows)]
    denominators = np.linalg.norm(eligible, axis=1) * np.linalg.norm(query)
    scores = np.divide(
        eligible @ query,
        denominators,
        out=np.zeros(len(rows), dtype=np.float32),
        where=denominators != 0,
    )
    return [(row, float(score)) for row, score in zip(rows, scores, strict=True)]


def rank_candidates(
    scored: list[tuple[int, float]],
    corpus: KnowledgeCorpus,
    category: str,
    *,
    min_score: float,
    top_n: int,
    top_k: int,
) -> list[tuple[int, float]]:
    """与 LiveVectorIndex.search 的判定顺序一致：阈值、top_n、类别优先重排、top_k。"""
    candidates = [(row, score) for row, score in scored if score >= min_score]
    if not candidates:
        return []
    initial = sorted(candidates, key=lambda item: item[1], reverse=True)[:top_n]
    return sorted(
        initial,
        key=lambda item: (category not in corpus.chunks[item[0]].categories, -item[1]),
    )[:top_k]


def build_hit(corpus: KnowledgeCorpus, row: int, score: float, rank: int) -> RetrievalHit:
    """与 LiveVectorIndex._hit 一致，使输出结构与真实运行记录可直接比较。"""
    chunk = corpus.chunks[row]
    rounded = round(score, 4)
    return RetrievalHit(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_title=chunk.document_title,
        section=chunk.section,
        content=chunk.content,
        source_uri=chunk.source_uri,
        retrieval_method="VECTOR",
        initial_rank=rank,
        initial_score=rounded,
        rerank_position=rank,
        rerank_score=rounded,
        used_as_evidence=True,
    )


def read_inputs(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"输入文件不是非空数组：{path}")
    for item in payload:
        if not isinstance(item.get("id"), str) or not isinstance(item.get("input"), dict):
            raise ValueError(f"输入条目缺少 id 或 input：{path}")
    return payload


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_plan(
    inputs: list[dict[str, Any]],
    corpus: KnowledgeCorpus,
    artifact_id: str,
    *,
    inputs_path: Path,
    corpus_path: Path,
    artifact_root: Path,
    model: str | None,
    dimension: int,
    chunking_version: str,
    top_n: int,
    top_k: int,
    min_score: float,
    category: str,
) -> dict[str, Any]:
    rows = [
        {
            "caseId": item["id"],
            "query": build_query(item["input"]["subject"], item["input"]["description"]),
        }
        for item in inputs
    ]
    return {
        "mode": MODE,
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "inputsFile": str(inputs_path),
        "inputsSha256": hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
        "corpusFile": str(corpus_path),
        "corpusSha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "corpusReleaseId": corpus.release_id,
        "corpusReleaseVersion": corpus.release_version,
        "corpusChecksum": corpus.corpus_checksum,
        "corpusChunkCount": len(corpus.chunks),
        "artifactRoot": str(artifact_root),
        "artifactId": artifact_id,
        "embeddingModel": model,
        "vectorDimension": dimension,
        "chunkingVersion": chunking_version,
        "allowedScopes": [scope.value for scope in ALLOWED_SCOPES],
        "topN": top_n,
        "topK": top_k,
        "minScore": min_score,
        "ticketCategory": category,
        "caseCount": len(rows),
        "plannedEmbeddingCalls": len(rows),
        "plannedGenerationCalls": 0,
        "distinctQueries": len({row["query"] for row in rows}),
        "querySha256": sha256_text("\n".join(row["query"] for row in rows)),
        "queries": rows,
    }


def write_new(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


async def run(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    inputs_path = (root / args.inputs).resolve()
    corpus_path = (root / args.corpus).resolve()
    artifact_root = (root / args.artifact_root).resolve()
    output = (root / args.output).resolve()

    settings = Settings(
        knowledge_path=corpus_path,
        embedding_artifact_root=artifact_root,
        embedding_artifact_build_policy="require-active",
        embedding_chunking_version=args.chunking_version,
    )
    corpus = load_knowledge_corpus(corpus_path)
    store = EmbeddingArtifactStore(settings, corpus)
    artifact = store.load_active()
    if (
        settings.embedding_vector_dimension is not None
        and artifact.manifest.vector_dimension != settings.embedding_vector_dimension
    ):
        raise ValueError(
            f"artifact 维度 {artifact.manifest.vector_dimension} 与配置 "
            f"{settings.embedding_vector_dimension} 不一致"
        )
    inputs = read_inputs(inputs_path)
    if args.limit is not None:
        inputs = inputs[: args.limit]

    plan = build_plan(
        inputs,
        corpus,
        artifact.manifest.artifact_id,
        inputs_path=inputs_path,
        corpus_path=corpus_path,
        artifact_root=artifact_root,
        model=settings.openai_embedding_model,
        dimension=artifact.manifest.vector_dimension,
        chunking_version=artifact.manifest.chunking_version,
        top_n=args.top_n,
        top_k=args.top_k,
        min_score=settings.live_retrieval_min_score,
        category=args.category,
    )

    if not args.execute:
        write_new(output / "retrieval-plan.json", plan)
        print(
            f"PREPARED mode={MODE} cases={plan['caseCount']} distinctQueries={plan['distinctQueries']} "
            f"embeddingCalls={plan['plannedEmbeddingCalls']} generationCalls=0"
        )
        return 0

    plan_file = output / "retrieval-plan.json"
    if plan_file.exists():
        existing = json.loads(plan_file.read_text(encoding="utf-8"))
        if existing.get("querySha256") != plan["querySha256"]:
            raise ValueError("已存在的计划与本次输入不一致；请换输出目录，不要覆盖既有证据")
    else:
        write_new(plan_file, plan)

    provider: EmbeddingProvider = OpenAIEmbeddingProvider(settings)
    rows_to_score = eligible_rows(corpus, ALLOWED_SCOPES)
    records: list[dict[str, Any]] = []
    vectors: dict[str, list[float]] = {}
    embedding_calls = 0
    for entry in plan["queries"]:
        case_id = entry["caseId"]
        query = entry["query"]
        query_vector = np.asarray(
            await provider.embed_query(redact_sensitive_text(query)),
            dtype=np.float32,
        )
        embedding_calls += 1
        if query_vector.ndim != 1 or query_vector.shape[0] != artifact.manifest.vector_dimension:
            raise ValueError(f"{case_id} 的 query 向量维度异常")
        vectors[case_id] = [float(value) for value in query_vector]
        scored = cosine_scores(artifact.matrix, query_vector, rows_to_score)
        ranked = rank_candidates(
            scored,
            corpus,
            args.category,
            min_score=settings.live_retrieval_min_score,
            top_n=args.top_n,
            top_k=args.top_k,
        )
        hits = [
            build_hit(corpus, row, score, rank).model_dump(mode="json")
            for rank, (row, score) in enumerate(ranked, start=1)
        ]
        records.append(
            {
                "caseId": case_id,
                "outcome": "RETRIEVED" if hits else "NO_EVIDENCE",
                "stages": {
                    "analyze": {
                        "body": {
                            "status": "OK",
                            "mode": MODE,
                            "retrieval": {"query": query, "hits": hits},
                        }
                    }
                },
            }
        )

    write_new(output / "results.json", records)
    write_new(output / "query-vectors.json", vectors)
    write_new(
        output / "retrieval-only-manifest.json",
        {
            **{key: value for key, value in plan.items() if key != "queries"},
            "executedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "executedCases": len(records),
            "executedEmbeddingCalls": embedding_calls,
            "executedGenerationCalls": 0,
            "casesWithHits": sum(1 for record in records if record["outcome"] == "RETRIEVED"),
        },
    )
    print(
        f"EXECUTED mode={MODE} cases={len(records)} embeddingCalls={embedding_calls} generationCalls=0 "
        f"casesWithHits={sum(1 for record in records if record['outcome'] == 'RETRIEVED')}"
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检索-only 离线评测（无生成调用）")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--inputs", default=DEFAULT_INPUTS)
    parser.add_argument("--corpus", default=DEFAULT_CORPUS)
    parser.add_argument("--artifact-root", default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--chunking-version", default=DEFAULT_CHUNKING_VERSION)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return anyio.run(run, parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
