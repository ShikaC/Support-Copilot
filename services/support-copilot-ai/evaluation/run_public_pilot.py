"""Run: .venv/bin/python -m evaluation.run_public_pilot PILOT_DIR NEW_RESULT_DIR.

Uses the service's locked environment and existing providers. All API calls are
sequential, have zero SDK retries, and use the existing configured timeout.
"""
import hashlib
import json
import math
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import anyio
import numpy as np
import typer
from numpy.typing import NDArray
from openai import OpenAIError
from pydantic import TypeAdapter

from app.config import Settings
from app.embedding_provider import OpenAIEmbeddingProvider
from app.observability import safe_provider_failure_details
from app.openai_provider import OpenAIProvider
from evaluation.public_pilot_data import (
    Chunk,
    CorpusIntegrityError,
    Dataset,
    Proposals,
    bm25_scores,
    load_chunks,
    proposed_evidence,
)
from evaluation.public_pilot_trial import Trial, TrialInput, pilot_access, run_trial


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def experiment(pilot: Path, output: Path) -> None:
    settings = Settings(ai_mode="live")
    dataset = Dataset.model_validate_json((pilot / "cases.json").read_text())
    proposals = Proposals.model_validate_json((pilot / "annotation-drafts.json").read_text())
    chunks = load_chunks(pilot)
    output.mkdir(parents=True, exist_ok=False)
    (output / "trials").mkdir()
    for filename in ("cases.json", "annotation-drafts.json", "annotation-evidence.json"):
        _ = (output / filename).write_bytes((pilot / filename).read_bytes())
    _ = (output / "chunks.json").write_bytes(TypeAdapter(list[Chunk]).dump_json(chunks, indent=2))
    source_files = sorted(Path("app").glob("*.py")) + sorted(Path("evaluation").glob("*public_pilot*.py"))
    sources = {str(path): sha(path) for path in source_files}
    code_snapshot = output / "source"
    for path in source_files:
        target = code_snapshot / path
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_bytes(path.read_bytes())
    manifest = {
        "started_at": datetime.now(UTC).isoformat(), "state": "RUNNING",
        "dataset_sha256": sha(pilot / "cases.json"), "chunks_sha256": sha(output / "chunks.json"),
        "source_hashes": sources, "documentation_version": "2.100.0", "cases": len(dataset.cases),
        "planned_trials": len(dataset.cases)*2 + len(proposals.cases), "chunk_count": len(chunks),
        "chat_model": settings.openai_chat_model, "embedding_model": settings.openai_embedding_model,
        "protocol": settings.openai_chat_protocol, "timeout_seconds": settings.openai_timeout_seconds,
        "sdk_retries": 0, "concurrency": 1, "top_k": 3, "chunking": "24-lines-stride-20-v1",
        "bm25": {"k1": 1.2, "b": 0.75, "tokenizer": "lowercase-ascii-alphanumeric"},
        "vector_min_score": settings.live_retrieval_min_score,
        "control": "AI-proposed-source-spans-not-human-gold; five cases only",
        "context_budget": "at most 3 chunks; same limit, actual lengths differ",
        "production_scope": "production embedding and generation providers; standalone retrieval; excludes Java, UI, risk policy and final reply rules",
        "latency_scope": "generation and local retrieval separately; document/query embedding batches recorded separately, not user request end-to-end latency",
        "human_reviewed": 0, "accuracy": None, "cost": None,
        "packages": {name: version(name) for name in ("openai", "langchain-openai", "numpy", "pydantic")},
    }
    _ = (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    texts = [f"{chunk.document_id}\n{chunk.content}" for chunk in chunks] + [case.input.question for case in dataset.cases]
    embedding = OpenAIEmbeddingProvider(settings)
    vectors: list[list[float]] = []
    embedding_start = perf_counter()
    for offset in range(0, len(texts), 16):
        try:
            with anyio.fail_after(90):
                batch = await embedding.embed_documents(texts[offset:offset+16])
        except (OpenAIError, TimeoutError) as exc:
            _ = (output / "embedding-error.json").write_text(json.dumps({"offset": offset,
                "error_type": type(exc).__name__, "diagnostics": safe_provider_failure_details(exc)}))
            typer.echo("Embedding stage failed; evidence preserved. No automatic retry.")
            raise typer.Exit(1) from None
        if len(batch) != len(texts[offset:offset+16]):
            raise CorpusIntegrityError("embedding-count-mismatch")
        vectors.extend(batch)
        typer.echo(f"embedding {len(vectors)}/{len(texts)}")
    matrix = np.asarray(vectors, dtype=np.float64)
    norms = [math.sqrt(sum(value*value for value in vector)) for vector in vectors]
    if not np.isfinite(matrix).all() or any(norm == 0 for norm in norms):
        raise CorpusIntegrityError("invalid-embedding-values")
    np.save(output / "embeddings.npy", matrix, allow_pickle=False)
    normalized = np.asarray([[value / norm for value in vector] for vector, norm in zip(vectors, norms, strict=True)], dtype=np.float64)
    _ = (output / "embedding-run.json").write_text(json.dumps({"vectors": len(vectors),
        "dimension": matrix.shape[1], "duration_ms": (perf_counter()-embedding_start)*1000,
        "sha256": sha(output / "embeddings.npy"), "batch_size": 16, "usage_tokens": None}))
    provider = OpenAIProvider(settings)
    access = pilot_access(sha(output / "chunks.json"))
    trials: list[Trial] = []
    proposal_by_id = {proposal.id: proposal for proposal in proposals.cases}
    for case_index, case in enumerate(dataset.cases):
        started = perf_counter()
        lexical = bm25_scores(chunks, case.input.question)
        lexical_ms = (perf_counter()-started)*1000
        started = perf_counter()
        query_vector = normalized[len(chunks)+case_index:len(chunks)+case_index+1].reshape(-1)
        dense_scores: NDArray[np.float64] = np.empty(len(chunks), dtype=np.float64)
        _ = np.dot(normalized[:len(chunks)], query_vector, out=dense_scores)
        dense = [dense_scores.item(index) for index in range(len(chunks))]
        dense_ms = (perf_counter()-started)*1000
        methods = [("bm25", lexical, lexical_ms, 0.0), ("vector", dense, dense_ms, settings.live_retrieval_min_score)]
        if case_index % 2:
            methods.reverse()
        inputs: list[TrialInput] = []
        for method, scores, duration, threshold in methods:
            ranked = sorted(range(len(chunks)), key=lambda index: (-scores[index], chunks[index].id))
            chosen = [index for index in ranked if scores[index] > threshold][:3]
            _ = (output / f"{case.id}-{method}-ranking.json").write_text(json.dumps([
                {"rank": rank, "chunk_id": chunks[index].id, "score": scores[index]}
                for rank, index in enumerate(ranked[:10], start=1)], indent=2))
            inputs.append(TrialInput(case, method, [chunks[index] for index in chosen], [scores[index] for index in chosen], duration))
        if case.id in proposal_by_id:
            context = proposed_evidence(pilot, proposal_by_id[case.id])
            inputs.append(TrialInput(case, "proposed_evidence", context[:3], [1.0]*min(3, len(context)), 0.0))
        for trial_input in inputs:
            trial = await run_trial(provider, trial_input, access)
            _ = (output / "trials" / f"{case.id}-{trial.method}.json").write_text(trial.model_dump_json(indent=2))
            trials.append(trial)
            typer.echo(f"{len(trials)}/{manifest['planned_trials']} {case.id} {trial.method} {trial.status} {trial.generation_ms:.0f}ms")
    _ = (output / "results.json").write_bytes(TypeAdapter(list[Trial]).dump_json(trials, indent=2))
    manifest["state"] = "COMPLETE_WITH_UNREVIEWED_OUTPUTS"
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    _ = (output / "manifest.json").write_text(json.dumps(manifest, indent=2))


def main(pilot: Path, output: Path) -> None:
    anyio.run(experiment, pilot.resolve(), output.resolve())


if __name__ == "__main__":
    typer.run(main)
