"""零调用诊断：gold 片段在全库中的真实排名，用来区分「召回不到」与「排序靠后」。

`scripts/benchmark/retrieval-eval.mjs` 回答的是「返回给模型的候选里有没有 gold」。
当 `top_k=3` 时，gold 排第 4 名与排第 400 名在结果上完全一样，但修复方向相反：
前者需要重排或融合，后者需要改切片或换 embedding。本工具用已缓存的 query 向量与
artifact 矩阵算出全库排名，并给出 recall@k 曲线——即「候选放到多大才能召回全部」。

零外部调用。用法：

    python -m evaluation.gold_rank \
      --vectors docs/verification/retrieval-only-2026-09-17/query-vectors.json
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import numpy as np

DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES = "docs/verification/quality-input-audit-2026-09-10/cases.json"
DEFAULT_CORPUS = "docs/verification/business-benchmark-2026-09-10/corpus.json"
DEFAULT_ARTIFACT_ROOT = ".local/business-benchmark-runtime/artifacts"
RECALL_POINTS = (1, 2, 3, 4, 6, 10)


def source_anchor(uri: str | None) -> str | None:
    """取出 source_uri 的 fragment 并解码，它是 Doc2Dial 的原始文档标识。"""
    if not uri:
        return None
    index = uri.find("#")
    if index < 0:
        return None
    return unquote(uri[index + 1 :])


def active_matrix(artifact_root: Path) -> tuple[str, np.ndarray]:
    pointer = json.loads((artifact_root / "active.json").read_text(encoding="utf-8"))
    artifact_id = pointer["active_artifact_id"]
    matrix = np.load(artifact_root / artifact_id / "matrix.npy")
    return artifact_id, matrix


def gold_rows(cases: list[dict[str, Any]], corpus: dict[str, Any]) -> dict[str, list[int]]:
    """把每题映射到 gold 文档在 corpus.chunks 中的全部行号。无标注的题不出现在结果里。"""
    rows_by_document: dict[str, list[int]] = {}
    document_by_anchor: dict[str, str] = {}
    for row, chunk in enumerate(corpus["chunks"]):
        rows_by_document.setdefault(chunk["document_id"], []).append(row)
        anchor = source_anchor(chunk.get("source_uri"))
        if anchor and anchor not in document_by_anchor:
            document_by_anchor[anchor] = chunk["document_id"]
    mapped: dict[str, list[int]] = {}
    for item in cases:
        anchor = (item.get("source") or {}).get("document_id")
        document_id = document_by_anchor.get(anchor) if anchor else None
        if document_id is not None:
            mapped[item["id"]] = rows_by_document[document_id]
    return mapped


def cosine_all(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
    return np.divide(
        matrix @ query,
        norms,
        out=np.zeros(matrix.shape[0], dtype=np.float32),
        where=norms != 0,
    )


def rank_case(scores: np.ndarray, rows: list[int], top: int = 3) -> dict[str, Any]:
    best_gold = float(scores[rows].max())
    order = np.argsort(-scores)[:top]
    return {
        "goldChunkCount": len(rows),
        "bestGoldScore": round(best_gold, 4),
        "bestGoldRank": int((scores > best_gold).sum()) + 1,
        "topScores": [round(float(scores[row]), 4) for row in order],
        "topInGold": [int(row) in set(rows) for row in order],
    }


def recall_curve(ranks: list[int], points: tuple[int, ...] = RECALL_POINTS) -> dict[str, int]:
    return {str(point): sum(1 for rank in ranks if rank <= point) for point in points}


def build_report(
    cases: list[dict[str, Any]],
    corpus: dict[str, Any],
    vectors: dict[str, list[float]],
    matrix: np.ndarray,
    artifact_id: str,
) -> dict[str, Any]:
    gold = gold_rows(cases, corpus)
    domains = {item["id"]: item.get("domain") for item in cases}
    rows: list[dict[str, Any]] = []
    for case_id, vector in vectors.items():
        if case_id not in gold:
            continue
        query = np.asarray(vector, dtype=np.float32)
        scores = cosine_all(matrix, query)
        rows.append({"caseId": case_id, "domain": domains.get(case_id), **rank_case(scores, gold[case_id])})
    ranks = [row["bestGoldRank"] for row in rows]
    return {
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "artifactId": artifact_id,
        "corpusChunkCount": len(corpus["chunks"]),
        "measuredCases": len(rows),
        "recallAtK": recall_curve(ranks),
        "cases": sorted(rows, key=lambda row: row["bestGoldRank"]),
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        "# gold 全库排名诊断",
        "",
        f"- artifact：`{report['artifactId'][:16]}…`，语料片段 {report['corpusChunkCount']}",
        f"- 测量题数：{report['measuredCases']}",
        "",
        "| k | 全库 recall@k |",
        "| ---: | ---: |",
    ]
    for point, hits in report["recallAtK"].items():
        lines.append(f"| {point} | {hits}/{report['measuredCases']} |")
    lines += [
        "",
        "| 题号 | 领域 | gold 片段 | gold 最佳分数 | 全库排名 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in report["cases"]:
        lines.append(
            f"| {row['caseId'][:28]} | {row['domain']} | {row['goldChunkCount']} | "
            f"{row['bestGoldScore']:.4f} | {row['bestGoldRank']} |"
        )
    lines += [
        "",
        "全库排名是诊断口径：产品上看的是返回候选（见 `scripts/benchmark/retrieval-eval.mjs`）。"
        "排名靠后但仍在靠前区间，说明需要重排或融合；排名很远，才说明召回本身有问题。",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="gold 全库排名诊断（零调用）")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--vectors", required=True, help="检索-only 运行产生的 query-vectors.json")
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--corpus", default=DEFAULT_CORPUS)
    parser.add_argument("--artifact-root", default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--json", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    vectors = json.loads((root / args.vectors).read_text(encoding="utf-8"))
    cases = json.loads((root / args.cases).read_text(encoding="utf-8"))
    corpus = json.loads((root / args.corpus).read_text(encoding="utf-8"))
    artifact_id, matrix = active_matrix((root / args.artifact_root).resolve())
    report = build_report(cases, corpus, vectors, matrix, artifact_id)
    if args.json:
        output = root / args.json
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
