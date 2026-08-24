from typing import Never

import anyio
import pytest

from app.analysis_runner import AnalysisProcessingTimeoutError, AnalysisRunner
from app.config import Settings
from app.models import AnalyzeRequest, TicketInput


class BlockingWorkflow:
    def __init__(self) -> None:
        self.cancelled = anyio.Event()

    async def run(self, request: AnalyzeRequest) -> Never:
        try:
            await anyio.sleep_forever()
        finally:
            self.cancelled.set()


class BrokenWorkflow:
    async def run(self, request: AnalyzeRequest) -> Never:
        raise TimeoutError("simulated internal timeout defect")


def analyze_request() -> AnalyzeRequest:
    return AnalyzeRequest(
        traceId="trace_processing_timeout",
        ticket=TicketInput(
            id="ticket-timeout",
            subject="企业账号无法登录",
            description="管理员和成员都无法进入工作区。",
            currentCategory="ACCOUNT_ACCESS",
        ),
    )


@pytest.mark.asyncio
async def test_processing_deadline_cancels_the_running_workflow() -> None:
    # Given: an analysis never completes within its configured total budget.
    workflow = BlockingWorkflow()
    settings = Settings(ai_processing_timeout_seconds=0.01, _env_file=None)
    runner = AnalysisRunner(settings, workflow)

    # When: the whole-analysis deadline expires.
    with pytest.raises(AnalysisProcessingTimeoutError) as error:
        await runner.run(analyze_request())

    # Then: cancellation reaches the running operation and keeps its trace context.
    assert workflow.cancelled.is_set()
    assert error.value.trace_id == "trace_processing_timeout"
    assert error.value.timeout_seconds == 0.01


@pytest.mark.asyncio
async def test_internal_timeout_error_is_not_misclassified() -> None:
    # Given: workflow code raises TimeoutError before the deadline owns cancellation.
    runner = AnalysisRunner(Settings(_env_file=None), BrokenWorkflow())

    # When/Then: the programming defect propagates instead of becoming a 504 deadline.
    with pytest.raises(TimeoutError, match="simulated internal timeout defect"):
        await runner.run(analyze_request())
