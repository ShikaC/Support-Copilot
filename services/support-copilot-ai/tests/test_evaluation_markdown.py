from typing import Final, get_args

import pytest

from evaluation.markdown import _render_case_failure
from evaluation.models import CaseFailure, CaseFailureMetric

FAILURE_RENDERING_CASES: Final = (
    (
        CaseFailure(
            metric="classification",
            expected="BILLING",
            actual="ACCOUNT_ACCESS",
        ),
        "- 分类：预期 BILLING，实际 ACCOUNT_ACCESS",
    ),
    (
        CaseFailure(metric="priority", expected="HIGH", actual="LOW"),
        "- 优先级：预期 HIGH，实际 LOW",
    ),
    (
        CaseFailure(metric="escalation", expected=True, actual=False),
        "- 人工升级：预期 True，实际 False",
    ),
    (
        CaseFailure(
            metric="citation",
            expected="retrieved_evidence_cited",
            actual="missing_citation",
        ),
        "- 引用：已检索到相关证据，但回复没有引用",
    ),
    (
        CaseFailure(
            metric="no_evidence_safety",
            expected="safe_fallback",
            actual="unsafe_response",
        ),
        "- 无证据安全：未使用无引用并升级人工复核的 fallback",
    ),
    (
        CaseFailure(
            metric="reply_constraint",
            expected="must_cite_evidence",
            actual="violated",
        ),
        "- 回复约束：未满足 must_cite_evidence",
    ),
)


def test_failure_rendering_cases_cover_every_allowed_metric() -> None:
    # Given: 模型定义允许类型，参数表声明已经测试的类型。
    allowed_metrics = set(get_args(CaseFailureMetric))
    tested_metrics = {failure.metric for failure, _ in FAILURE_RENDERING_CASES}

    # When / Then: 两份名单必须完全一致，新增类型不能在没有显示测试时通过。
    assert tested_metrics == allowed_metrics


@pytest.mark.parametrize(
    ("failure", "expected_line"),
    FAILURE_RENDERING_CASES,
    ids=tuple(failure.metric for failure, _ in FAILURE_RENDERING_CASES),
)
def test_renders_every_case_failure_type(
    failure: CaseFailure,
    expected_line: str,
) -> None:
    # Given: 参数列表分别提供每种合法的结构化错误。
    # When: 报告层把当前错误转换成一行 Markdown。
    line = _render_case_failure(failure)

    # Then: 每种错误都使用对应的中文说明，不会遗漏显示分支。
    assert line == expected_line
