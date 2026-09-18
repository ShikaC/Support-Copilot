"""零调用融合实验：在缓存的向量排名上叠加 BM25，用 RRF 融合，比较 gold 命中。

向量检索的全库排名显示 gold 已经落在前 6 名内，瓶颈是排序精度而不是召回。
本工具用于在同一批题目、同一语料、同一 gold 口径下比较「纯向量」与「向量 + BM25 融合」，
全程使用已缓存的 query 向量与本地语料，不产生任何外部调用。

纪律：主对比只有一组（等权 RRF，k=60）。其余配置是敏感性分析，11 题的样本量下
很容易过拟合，不能当作已验证的改进；任何最终参数都需要在新数据上复验。
"""

import argparse
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from evaluation.gold_rank import active_matrix, cosine_all, gold_rows

DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = "docs/verification/retrieval-only-2026-09-17/retrieval-plan.json"
DEFAULT_VECTORS = "docs/verification/retrieval-only-2026-09-17/query-vectors.json"
DEFAULT_CASES = "docs/verification/quality-input-audit-2026-09-10/cases.json"
DEFAULT_CORPUS = "docs/verification/business-benchmark-2026-09-10/corpus.json"
DEFAULT_ARTIFACT_ROOT = ".local/business-benchmark-runtime/artifacts"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
BM25_K1 = 1.2
BM25_B = 0.75
PRIMARY = {"name": "rrf-equal-k60", "rrfK": 60, "vectorWeight": 1.0, "bm25Weight": 1.0}
SENSITIVITY = (
    {"name": "vector-only", "rrfK": 60, "vectorWeight": 1.0, "bm25Weight": 0.0},
    {"name": "bm25-only", "rrfK": 60, "vectorWeight": 0.0, "bm25Weight": 1.0},
    {"name": "rrf-equal-k10", "rrfK": 10, "vectorWeight": 1.0, "bm25Weight": 1.0},
    {"name": "rrf-equal-k100", "rrfK": 100, "vectorWeight": 1.0, "bm25Weight": 1.0},
    {"name": "rrf-bm25x0.5-k60", "rrfK": 60, "vectorWeight": 1.0, "bm25Weight": 0.5},
    {"name": "rrf-bm25x2-k60", "rrfK": 60, "vectorWeight": 1.0, "bm25Weight": 2.0},
)


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


class BM25:
    """Okapi BM25，只为离线比较服务，不进入生产路径。"""

    def __init__(self, documents: list[str], k1: float = BM25_K1, b: float = BM25_B) -> None:
        frequencies = [Counter(tokenize(document)) for document in documents]
        lengths = np.asarray([sum(count.values()) for count in frequencies], dtype=np.float32)
        average = float(lengths.mean()) if lengths.size else 0.0
        # 全空语料时避免除以 0；长度归一化退化为常数。
        self._average = average if average > 0 else 1.0
        self._lengths = lengths
        self._k1 = k1
        self._b = b
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for row, frequency in enumerate(frequencies):
            for term, count in frequency.items():
                self._postings.setdefault(term, []).append((row, count))
        total = len(documents)
        self._idf = {
            term: math.log(1 + (total - len(postings) + 0.5) / (len(postings) + 0.5))
            for term, postings in self._postings.items()
        }

    def scores(self, query: str) -> np.ndarray:
        scores = np.zeros(len(self._lengths), dtype=np.float32)
        for term in set(tokenize(query)):
            idf = self._idf.get(term)
            if idf is None:
                continue
            for row, count in self._postings[term]:
                denominator = count + self._k1 * (
                    1 - self._b + self._b * self._lengths[row] / self._average
                )
                scores[row] += idf * count * (self._k1 + 1) / denominator
        return scores


def ranks_of(scores: np.ndarray) -> np.ndarray:
    """返回每个下标的 1-based 排名（分数高者排名靠前）。"""
    order = np.argsort(-scores, kind="stable")
    ranks = np.empty(scores.shape[0], dtype=np.float32)
    ranks[order] = np.arange(1, scores.shape[0] + 1, dtype=np.float32)
    return ranks


def rrf(rankings: list[np.ndarray], weights: list[float], k: int) -> np.ndarray:
    """Reciprocal Rank Fusion：权重为 0 的 ranker 完全不参与。"""
    total = np.zeros(rankings[0].shape[0], dtype=np.float64)
    for ranks, weight in zip(rankings, weights, strict=True):
        if weight == 0:
            continue
        total += weight / (k + ranks)
    return total


def evaluate_case(fused: np.ndarray, gold: list[int], top_k: int) -> dict[str, Any]:
    order = np.argsort(-fused, kind="stable")[:top_k]
    gold_set = set(gold)
    first = next((rank for rank, row in enumerate(order, start=1) if int(row) in gold_set), None)
    return {"firstGoldRank": first, "topInGold": [int(row) in gold_set for row in order]}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [row["firstGoldRank"] for row in rows]
    at = lambda limit: sum(1 for rank in ranks if rank is not None and rank <= limit)  # noqa: E731
    return {
        "cases": len(rows),
        "goldAt1": at(1),
        "goldAt3": at(3),
        "mrr": round(sum(1 / rank for rank in ranks if rank is not None) / len(ranks), 4),
    }


def mcnemar_exact(improved: int, degraded: int) -> float:
    """配对二值比较的精确检验双侧 p 值（只看结果不一致的题）。"""
    total = improved + degraded
    if total == 0:
        return 1.0
    smaller = min(improved, degraded)
    tail = sum(math.comb(total, index) for index in range(smaller + 1)) / 2**total
    return min(1.0, 2 * tail)


def compare_configs(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """比较两组配置在该题集上的命中变化，并给出能否区分于随机的 p 值。"""
    hit = lambda row: row["firstGoldRank"] is not None  # noqa: E731
    improved, degraded = [], []
    for row, base in zip(candidate["rows"], baseline["rows"], strict=True):
        if hit(row) and not hit(base):
            improved.append(row["caseId"])
        elif hit(base) and not hit(row):
            degraded.append(row["caseId"])
    return {
        "baseline": baseline["name"],
        "improved": improved,
        "degraded": degraded,
        "pValue": round(mcnemar_exact(len(improved), len(degraded)), 4),
        "conclusive": len(improved) + len(degraded) >= 6,
    }


def evaluate_config(
    config: dict[str, Any],
    case_ids: list[str],
    vector_ranks: dict[str, np.ndarray],
    bm25_ranks: dict[str, np.ndarray],
    gold: dict[str, list[int]],
    top_k: int,
) -> dict[str, Any]:
    rows = []
    for case_id in case_ids:
        fused = rrf(
            [vector_ranks[case_id], bm25_ranks[case_id]],
            [config["vectorWeight"], config["bm25Weight"]],
            config["rrfK"],
        )
        rows.append({"caseId": case_id, **evaluate_case(fused, gold[case_id], top_k)})
    return {**config, "summary": summarize(rows), "rows": rows}


def build_experiment(
    plan: dict[str, Any],
    vectors: dict[str, list[float]],
    cases: list[dict[str, Any]],
    corpus: dict[str, Any],
    matrix: np.ndarray,
    *,
    top_k: int,
) -> dict[str, Any]:
    gold = gold_rows(cases, corpus)
    case_ids = [
        entry["caseId"]
        for entry in plan["queries"]
        if entry["caseId"] in vectors and entry["caseId"] in gold
    ]
    queries = {entry["caseId"]: entry["query"] for entry in plan["queries"]}
    bm25 = BM25([chunk["content"] for chunk in corpus["chunks"]])
    vector_ranks = {
        case_id: ranks_of(cosine_all(matrix, np.asarray(vectors[case_id], dtype=np.float32)))
        for case_id in case_ids
    }
    bm25_ranks = {case_id: ranks_of(bm25.scores(queries[case_id])) for case_id in case_ids}
    primary = evaluate_config(PRIMARY, case_ids, vector_ranks, bm25_ranks, gold, top_k)
    sensitivity = [
        evaluate_config(config, case_ids, vector_ranks, bm25_ranks, gold, top_k)
        for config in SENSITIVITY
    ]
    vector_only = next(config for config in sensitivity if config["name"] == "vector-only")
    return {
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "measuredCases": len(case_ids),
        "topK": top_k,
        "corpusChunkCount": len(corpus["chunks"]),
        "bm25": {"k1": BM25_K1, "b": BM25_B, "fields": ["content"]},
        "primary": primary,
        "sensitivity": sensitivity,
        "primaryVersusVectorOnly": compare_configs(primary, vector_only),
    }


def render(report: dict[str, Any]) -> str:
    def line(config: dict[str, Any]) -> str:
        summary = config["summary"]
        return (
            f"| {config['name']} | k={config['rrfK']} | "
            f"{config['vectorWeight']} / {config['bm25Weight']} | "
            f"{summary['goldAt1']}/{summary['cases']} | {summary['goldAt3']}/{summary['cases']} | "
            f"{summary['mrr']:.3f} |"
        )

    lines = [
        "# 融合检索实验（零调用）",
        "",
        f"- 测量题数：{report['measuredCases']}，语料片段 {report['corpusChunkCount']}，top_k={report['topK']}",
        f"- BM25 参数：k1={report['bm25']['k1']}、b={report['bm25']['b']}，索引字段 {report['bm25']['fields']}",
        "",
        "## 主对比（先定方案，后看结果）",
        "",
        "| 配置 | RRF k | 权重 向量/BM25 | gold@1 | gold@3 | MRR |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
        line(report["primary"]),
        "",
        "## 敏感性分析（同一批题上选参数，不足以证明泛化）",
        "",
        "| 配置 | RRF k | 权重 向量/BM25 | gold@1 | gold@3 | MRR |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    lines += [line(config) for config in report["sensitivity"]]
    comparison = report["primaryVersusVectorOnly"]
    lines += [
        "",
        "## 主对比 vs 纯向量（能否区分于随机）",
        "",
        f"- 改善：{len(comparison['improved'])} 题；退化：{len(comparison['degraded'])} 题",
        f"- 精确配对检验双侧 p 值：{comparison['pValue']}（{'可区分' if comparison['pValue'] < 0.05 else '无法区分于随机'}）",
        f"- 不一致题数 {len(comparison['improved']) + len(comparison['degraded'])}："
        f"{'样本量足以支撑结论' if comparison['conclusive'] else '远低于任何有意义结论所需的样本量'}",
        "",
        "`vector-only` 与 `bm25-only` 是框架自检：前者必须复现已知的纯向量基线。",
        "MRR 只在返回的前 top_k 内计分，未命中记 0；全库口径见 `evaluation/gold_rank.py`。",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="零调用融合检索实验")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--plan", default=DEFAULT_PLAN)
    parser.add_argument("--vectors", default=DEFAULT_VECTORS)
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--corpus", default=DEFAULT_CORPUS)
    parser.add_argument("--artifact-root", default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", default=None)
    parser.add_argument("--markdown", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    plan = json.loads((root / args.plan).read_text(encoding="utf-8"))
    vectors = json.loads((root / args.vectors).read_text(encoding="utf-8"))
    cases = json.loads((root / args.cases).read_text(encoding="utf-8"))
    corpus = json.loads((root / args.corpus).read_text(encoding="utf-8"))
    _, matrix = active_matrix((root / args.artifact_root).resolve())
    report = build_experiment(plan, vectors, cases, corpus, matrix, top_k=args.top_k)
    if args.json:
        (root / args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    rendered = render(report)
    if args.markdown:
        (root / args.markdown).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
