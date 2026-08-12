from collections.abc import Awaitable, Callable, Sequence

from app.models import AnalyzeOptions, AnalyzeRequest, AnalyzeResponse
from evaluation.models import EvaluationCase


async def analyze_cases(
    cases: Sequence[EvaluationCase],
    analyze: Callable[[AnalyzeRequest], Awaitable[AnalyzeResponse]],
    options: AnalyzeOptions,
) -> tuple[AnalyzeResponse, ...]:
    responses: list[AnalyzeResponse] = []
    for case in cases:
        responses.append(await analyze(case.to_request(options)))
    return tuple(responses)
