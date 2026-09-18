import numpy as np
import pytest

from evaluation import hybrid_retrieval as hybrid


def corpus_fixture() -> dict:
    return {
        "release_id": "fixture",
        "release_version": 1,
        "corpus_checksum": "0" * 64,
        "chunks": [
            {
                "chunk_id": "a-0",
                "document_id": "doc-a",
                "content": "driver civil penalty online payment instructions",
                "source_uri": "kb://doc-a/v1#Pay%20driver%20civil%20penalty",
            },
            {
                "chunk_id": "b-0",
                "document_id": "doc-b",
                "content": "unrelated benefit recertification guidance",
                "source_uri": "kb://doc-b/v1#Other",
            },
            {
                "chunk_id": "a-1",
                "document_id": "doc-a",
                "content": "penalty payment portal requirements",
                "source_uri": "kb://doc-a/v1#Pay%20driver%20civil%20penalty",
            },
        ],
    }


def plan_fixture() -> dict:
    return {
        "queries": [
            {"caseId": "case-1", "query": "civil penalty online payment"},
            {"caseId": "case-2", "query": "recertification guidance"},
        ]
    }


def test_tokenize_lowercases_and_splits_on_punctuation() -> None:
    assert hybrid.tokenize("Pay driver civil penalty #1_0 (online)!") == [
        "pay",
        "driver",
        "civil",
        "penalty",
        "1",
        "0",
        "online",
    ]


def test_bm25_prefers_the_document_containing_the_query_terms() -> None:
    bm25 = hybrid.BM25(["driver penalty payment", "unrelated guidance"])
    scores = bm25.scores("driver penalty")
    assert scores[0] > scores[1]
    assert scores[1] == 0


def test_bm25_ignores_unknown_terms_and_empty_queries() -> None:
    bm25 = hybrid.BM25(["driver penalty", "guidance"])
    assert np.allclose(bm25.scores("nonexistentterm"), 0)
    assert np.allclose(bm25.scores(""), 0)


def test_bm25_handles_an_empty_corpus_without_dividing_by_zero() -> None:
    bm25 = hybrid.BM25([])
    assert bm25.scores("anything").shape == (0,)


def test_ranks_of_gives_rank_one_to_the_highest_score() -> None:
    ranks = hybrid.ranks_of(np.asarray([0.1, 0.9, 0.5], dtype=np.float32))
    assert list(ranks) == [3.0, 1.0, 2.0]


def test_rrf_ignores_zero_weight_rankers() -> None:
    # rrf 的参数是排名而不是分数：rank 越小贡献越大。
    vector_scores = np.asarray([0.1, 0.9, 0.5], dtype=np.float32)
    bm25_scores = np.asarray([0.9, 0.1, 0.5], dtype=np.float32)
    vector_ranks = hybrid.ranks_of(vector_scores)
    bm25_ranks = hybrid.ranks_of(bm25_scores)
    assert list(vector_ranks) == [3.0, 1.0, 2.0]
    assert list(bm25_ranks) == [1.0, 3.0, 2.0]

    only_vector = hybrid.rrf([vector_ranks, bm25_ranks], [1.0, 0.0], 60)
    # rrf 分数降序等价于 rank 升序。
    assert list(np.argsort(-only_vector)) == list(np.argsort(vector_ranks)) == [1, 2, 0]

    # 等权时两个「一升一降」的文档得分相同，而两边都排第二的文档更低。
    combined = hybrid.rrf([vector_ranks, bm25_ranks], [1.0, 1.0], 60)
    assert combined[0] == pytest.approx(combined[1])
    assert combined[0] > combined[2]


def test_evaluate_case_reports_the_first_gold_rank() -> None:
    fused = np.asarray([0.9, 0.8, 0.7, 0.6], dtype=np.float64)
    result = hybrid.evaluate_case(fused, [2], top_k=3)
    assert result["firstGoldRank"] == 3
    assert result["topInGold"] == [False, False, True]
    assert hybrid.evaluate_case(fused, [3], top_k=3)["firstGoldRank"] is None


def test_summarize_computes_gold_at_k_and_mrr() -> None:
    rows = [
        {"firstGoldRank": 1},
        {"firstGoldRank": 3},
        {"firstGoldRank": None},
        {"firstGoldRank": 2},
    ]
    summary = hybrid.summarize(rows)
    assert summary["goldAt1"] == 1
    assert summary["goldAt3"] == 3
    assert summary["cases"] == 4
    assert summary["mrr"] == pytest.approx(round((1 + 1 / 3 + 0 + 1 / 2) / 4, 4))


def test_vector_only_matches_a_plain_vector_ranking() -> None:
    """框架自检：权重为 0 的 BM25 不得改变向量排序结果。"""
    corpus = corpus_fixture()
    matrix = np.asarray(
        [[0.9, 0.1], [0.2, 0.8], [0.85, 0.15]],
        dtype=np.float32,
    )
    vectors = {"case-1": [1.0, 0.0], "case-2": [0.0, 1.0]}
    cases = [
        {"id": "case-1", "domain": "dmv", "source": {"document_id": "Pay driver civil penalty"}},
        {"id": "case-2", "domain": "ssa", "source": {"document_id": "Other"}},
    ]
    report = hybrid.build_experiment(plan_fixture(), vectors, cases, corpus, matrix, top_k=3)
    vector_only = next(
        config for config in report["sensitivity"] if config["name"] == "vector-only"
    )
    expected = hybrid.summarize(
        [
            {
                "firstGoldRank": hybrid.evaluate_case(
                    hybrid.cosine_all(matrix, np.asarray(vectors[case_id], dtype=np.float32)),
                    [0, 2] if case_id == "case-1" else [1],
                    top_k=3,
                )["firstGoldRank"]
            }
            for case_id in ("case-1", "case-2")
        ]
    )
    assert vector_only["summary"] == expected


def test_build_experiment_only_measures_cases_with_gold_and_vectors() -> None:
    report = hybrid.build_experiment(
        {
            "queries": [
                {"caseId": "case-1", "query": "civil penalty"},
                {"caseId": "no-gold", "query": "x"},
                {"caseId": "no-vector", "query": "y"},
            ]
        },
        {"case-1": [1.0, 0.0], "no-gold": [1.0, 0.0]},
        [{"id": "case-1", "source": {"document_id": "Pay driver civil penalty"}}],
        corpus_fixture(),
        np.asarray([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
        top_k=3,
    )
    assert report["measuredCases"] == 1
    assert report["primary"]["summary"]["cases"] == 1


def test_mcnemar_exact_matches_the_binomial_tail() -> None:
    # b=2、c=1 时 n=3，双侧 p = 2 * P(X<=1) = 1.0，样本量不足时不应给出显著结论。
    assert hybrid.mcnemar_exact(2, 1) == 1.0
    # 完全没有不一致的题时无法拒绝原假设。
    assert hybrid.mcnemar_exact(0, 0) == 1.0
    # 一边倒时 p 值必须足够小。
    assert hybrid.mcnemar_exact(10, 0) < 0.01


def test_compare_configs_lists_improved_and_degraded_cases() -> None:
    baseline = {"name": "vector-only", "rows": [{"caseId": "a", "firstGoldRank": 1}, {"caseId": "b", "firstGoldRank": None}]}
    candidate = {"name": "rrf", "rows": [{"caseId": "a", "firstGoldRank": None}, {"caseId": "b", "firstGoldRank": 2}]}
    comparison = hybrid.compare_configs(candidate, baseline)
    assert comparison["improved"] == ["b"]
    assert comparison["degraded"] == ["a"]
    assert comparison["pValue"] == 1.0
    assert comparison["conclusive"] is False


def test_build_experiment_reports_primary_against_vector_only() -> None:
    report = hybrid.build_experiment(
        plan_fixture(),
        {"case-1": [1.0, 0.0], "case-2": [0.0, 1.0]},
        [
            {"id": "case-1", "source": {"document_id": "Pay driver civil penalty"}},
            {"id": "case-2", "source": {"document_id": "Other"}},
        ],
        corpus_fixture(),
        np.asarray([[0.9, 0.1], [0.2, 0.8], [0.85, 0.15]], dtype=np.float32),
        top_k=3,
    )
    comparison = report["primaryVersusVectorOnly"]
    assert comparison["baseline"] == "vector-only"
    assert set(comparison) == {"baseline", "improved", "degraded", "pValue", "conclusive"}
