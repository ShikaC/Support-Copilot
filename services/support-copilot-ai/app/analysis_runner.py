from typing import Protocol

import anyio

from app.config import Settings
from app.models import AnalyzeRequest, AnalyzeResponse


class AnalysisOperation(Protocol):
    async def run(self, request: AnalyzeRequest) -> AnalyzeResponse: ...


class AnalysisProcessingTimeoutError(Exception):
    def __init__(self, trace_id: str, timeout_seconds: float) -> None:
        self.trace_id = trace_id
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Analysis {trace_id} exceeded {timeout_seconds:g} seconds"
        )


class AnalysisRunner:
    def __init__(self, settings: Settings, operation: AnalysisOperation) -> None:
        self._settings = settings
        self._operation = operation

    async def run(self, request: AnalyzeRequest) -> AnalyzeResponse:
        deadline_scope: anyio.CancelScope | None = None
        try:
            with anyio.fail_after(
                self._settings.ai_processing_timeout_seconds
            ) as deadline_scope:
                return await self._operation.run(request)
        except TimeoutError as exc:
            if deadline_scope is None or not deadline_scope.cancelled_caught:
                raise
            raise AnalysisProcessingTimeoutError(
                trace_id=request.trace_id,
                timeout_seconds=self._settings.ai_processing_timeout_seconds,
            ) from exc
