import json
from pathlib import Path

import numpy as np
import pytest

from evaluation import gold_rank


def corpus_fixture() -> dict:
    return {
        "release_id": "fixture",
        "release_version": 1,
        "corpus_checksum": "0" * 64,
        "chunks": [
            {
                "chunk_id": "a-0",
                "document_id": "doc-a",
                "source_uri": "kb://doc-a/v1#Pay%20driver%20civil%20penalty%231_0",
            },
            {"chunk_id": "b-0", "document_id": "doc-b", "source_uri": "kb://doc-b/v1#Other%20doc"},
            {"chunk_id": "a-1", "document_id": "doc-a", "source_uri": "kb://doc-a/v1#Pay%20driver%20civil%20penalty%231_0"},
            {"chunk_id": "c-0", "document_id": "doc-c", "source_uri": None},
        ],
    }


def test_source_anchor_decodes_fragment() -> None:
    assert gold_rank.source_anchor("kb://doc-a/v1#Pay%20driver") == "Pay driver"
    assert gold_rank.source_anchor("kb://doc-a/v1") is None
    assert gold_rank.source_anchor(None) is None


def test_gold_rows_maps_every_chunk_of_the_labeled_document() -> None:
    cases = [
        {"id": "case-1", "source": {"document_id": "Pay driver civil penalty#1_0"}},
        {"id": "case-2", "source": {"document_id": "Unknown doc"}},
        {"id": "case-3", "source": {}},
    ]
    mapped = gold_rank.gold_rows(cases, corpus_fixture())
    # 同一文档被切成多个片段时，全部片段都算 gold；没有标注的题不参与统计。
    assert mapped == {"case-1": [0, 2]}


def test_rank_case_reports_the_highest_gold_score_and_its_global_rank() -> None:
    scores = np.asarray([0.5, 0.9, 0.7], dtype=np.float32)
    result = gold_rank.rank_case(scores, [0])
    assert result["bestGoldScore"] == 0.5
    assert result["bestGoldRank"] == 3
    assert result["topScores"] == [0.9, 0.7, 0.5]
    assert result["topInGold"] == [False, False, True]


def test_recall_curve_counts_how_many_candidates_are_needed() -> None:
    curve = gold_rank.recall_curve([1, 2, 4, 9])
    assert curve == {"1": 1, "2": 2, "3": 2, "4": 3, "6": 3, "10": 4}


def test_build_report_distinguishes_ranking_from_recall(tmp_path: Path) -> None:
    matrix = np.asarray(
        [
            [0.6, 1.0],
            [1.0, 0.05],
            [0.5, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )
    cases = [
        {"id": "case-1", "domain": "dmv", "source": {"document_id": "Pay driver civil penalty#1_0"}},
    ]
    # 行 1 与 query 最相似且属于另一份文档，因此 gold（行 0、行 2）最佳排名是第 2：
    # 这正是本工具要区分的"排序靠后"而非"没召回"。
    report = gold_rank.build_report(
        cases, corpus_fixture(), {"case-1": [1.0, 0.05]}, matrix, "artifact-fixture"
    )
    assert report["measuredCases"] == 1
    assert report["recallAtK"]["1"] == 0
    assert report["recallAtK"]["3"] == 1
    assert report["cases"][0]["bestGoldRank"] == 2


def test_build_report_ignores_cases_without_cached_vectors() -> None:
    report = gold_rank.build_report([], corpus_fixture(), {}, np.zeros((4, 2)), "artifact-fixture")
    assert report["measuredCases"] == 0
    assert report["recallAtK"]["3"] == 0


def test_cli_refuses_raw_matrix_without_recorded_evidence(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "abc123").mkdir(parents=True)
    np.save(artifact_root / "abc123" / "matrix.npy", np.eye(2, dtype=np.float32))
    (artifact_root / "active.json").write_text(
        json.dumps({"schema_version": 1, "active_artifact_id": "abc123", "previous_artifact_id": None}),
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        gold_rank.main([
            "--root", str(tmp_path), "--vectors", "query-vectors.json",
            "--artifact-root", "artifacts", "--json", "report.json",
        ])
    assert not (tmp_path / "report.json").exists()


def test_render_states_the_diagnostic_boundary() -> None:
    report = gold_rank.build_report(
        [{"id": "case-1", "domain": "dmv", "source": {"document_id": "Pay driver civil penalty#1_0"}}],
        corpus_fixture(),
        {"case-1": [1.0, 0.0]},
        np.asarray(
            [[0.6, 1.0], [1.0, 0.05], [0.5, 1.0], [0.0, 1.0]], dtype=np.float32
        ),
        "artifact-fixture",
    )
    rendered = gold_rank.render(report)
    assert "全库排名是诊断口径" in rendered
    assert "artifact-fixture"[:16] in rendered
    assert "1/1" in rendered


def test_missing_vectors_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        gold_rank.main(
            [
                "--root", str(tmp_path),
                "--vectors", "missing.json",
                "--cases", "cases.json",
                "--corpus", "corpus.json",
                "--artifact-root", "artifacts",
            ]
        )
