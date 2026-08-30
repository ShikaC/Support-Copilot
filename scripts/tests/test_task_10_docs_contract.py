import shutil
from pathlib import Path

import pytest

from scripts.source_contracts import FASTAPI_MAIN, JAVA_CONTROLLER_ROOT
from scripts.verify_docs import (
    AI_CONFIG,
    OPERATIONS_DOC,
    RELEASE_SURFACES,
    TASK_10_ATTEMPT_3_HEADING,
    VERIFIER_SCRIPT,
    validate_release_contract,
)


def copy_release_fixture(destination: Path) -> None:
    source_root = Path(__file__).resolve().parents[2]
    paths = [
        *(source_root / path for path in RELEASE_SURFACES),
        source_root / AI_CONFIG,
        source_root / "services/support-copilot-ai/.env.example",
        source_root / FASTAPI_MAIN,
        source_root / VERIFIER_SCRIPT,
        *(source_root / JAVA_CONTROLLER_ROOT).rglob("*Controller.java"),
        *(source_root / "services/support-copilot-api/src/main/resources").glob(
            "application-*.properties"
        ),
    ]
    for source in paths:
        target = destination / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


@pytest.mark.parametrize(
    ("truth", "false_claim", "boundary"),
    [
        ("`be9ac60` 上的 Responses 协议 4-case 报告首次观察到 1 case live success、3 case `invalid_model_response` fallback", "`be9ac60` 上的 Responses 协议 4-case 报告证明完整 dataset success；保留 3 case `invalid_model_response` fallback 和 1 case live success 计数", "responses-dataset-failures"),
        ("第二次 Responses 协议受限运行再次得到相同的 1 live success / 3 `invalid_model_response` fallback", "第二次 Responses 协议受限运行证明 `b8560190583fc2888f2428353ffcb43caac6cbc3` 完整 dataset success；保留 3 `invalid_model_response` fallback / 1 live success 计数", "responses-dataset-failures"),
        ("两次都是明确失败的历史 dataset evidence", "两次都证明完整 dataset success", "responses-dataset-failures"),
        ("0/4 `NOT_REVIEWED`", "4/4 `NOT_REVIEWED`", "human-review-incomplete"),
    ],
)
def test_release_contract_rejects_false_live_evidence_claims(
    tmp_path: Path, truth: str, false_claim: str, boundary: str
) -> None:
    # Given: a current release fixture with one truth boundary changed to success.
    copy_release_fixture(tmp_path)
    readme = tmp_path / "README.md"
    valid = readme.read_text(encoding="utf-8")
    mutated = valid.replace(truth, false_claim)
    assert mutated != valid
    readme.write_text(mutated, encoding="utf-8")

    # When/Then: tokens remain, but the bound false claim fails closed.
    errors = validate_release_contract(tmp_path)
    assert f"README.md: missing canonical live evidence boundary: {boundary}" in errors


@pytest.mark.parametrize(
    "removed_fact",
    (
        "`bfb7eee6adae0556399e56457eeed19a158c1d39`",
        "`chat_completions`",
        "React -> Java -> Python -> Java",
        "1 success、3 个 `invalid_model_response` fallback",
        "0/4 `NOT_REVIEWED`",
        "`publishable=false`",
        "`f7ccdb0`",
        "`d0234e4`",
    ),
)
def test_release_contract_binds_task_10_attempt_3_claim_to_its_canonical_paragraph(
    tmp_path: Path, removed_fact: str
) -> None:
    # Given: the canonical attempt-3 paragraph with one required fact removed.
    copy_release_fixture(tmp_path)
    readme = tmp_path / "README.md"
    valid = readme.read_text(encoding="utf-8")
    heading_end = valid.index(TASK_10_ATTEMPT_3_HEADING) + len(
        TASK_10_ATTEMPT_3_HEADING
    )
    paragraph_start = heading_end + 2
    paragraph_end = valid.index("\n\n", paragraph_start)
    paragraph = valid[paragraph_start:paragraph_end]
    mutated = (
        valid[:paragraph_start]
        + paragraph.replace(removed_fact, "[removed]")
        + valid[paragraph_end:]
    )
    assert mutated != valid
    readme.write_text(mutated, encoding="utf-8")

    # When: the release contract is checked.
    errors = validate_release_contract(tmp_path)

    # Then: the fact cannot be satisfied by a free-floating copy elsewhere.
    assert (
        "README.md: missing canonical live evidence boundary: "
        "task-10-chat-completions-attempt-3"
    ) in errors


def test_release_contract_rejects_stale_chat_completions_relay_only_claim(
    tmp_path: Path,
) -> None:
    # Given: the anchored attempt-3 record is replaced with the retired relay-only claim.
    copy_release_fixture(tmp_path)
    readme = tmp_path / "README.md"
    valid = readme.read_text(encoding="utf-8")
    heading_end = valid.index(TASK_10_ATTEMPT_3_HEADING) + len(
        TASK_10_ATTEMPT_3_HEADING
    )
    paragraph_start = heading_end + 2
    paragraph_end = valid.index("\n\n", paragraph_start)
    stale = (
        "Chat Completions relay only completed one synthetic direct-provider probe; "
        "the full dataset is still pending."
    )
    mutated = valid[:paragraph_start] + stale + valid[paragraph_end:]
    readme.write_text(mutated, encoding="utf-8")

    # When: the release contract is checked.
    errors = validate_release_contract(tmp_path)

    # Then: retired wording cannot satisfy the attempt-3 evidence contract.
    assert (
        "README.md: missing canonical live evidence boundary: "
        "task-10-chat-completions-attempt-3"
    ) in errors
