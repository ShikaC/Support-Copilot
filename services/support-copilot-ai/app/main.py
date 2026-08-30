import logging
import re
from collections.abc import Awaitable, Callable
from typing import Annotated, Final
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.analysis_runner import AnalysisProcessingTimeoutError, AnalysisRunner
from app.config import get_settings
from app.internal_auth import (
    InternalServiceAuthenticationError,
    InternalServiceAuthenticator,
)
from app.knowledge import KnowledgeReleaseMismatchError, KnowledgeRetriever
from app.models import TRACE_ID_PATTERN, AnalyzeRequest, AnalyzeResponse
from app.workflow import AnalysisWorkflow

STRUCTURED_LOG_FORMAT: Final = (
    "%(asctime)s %(levelname)s %(name)s event=%(message)s "
    "trace_id=%(trace_id)s timeout_seconds=%(timeout_seconds)s "
    "error_code=%(error_code)s error_type=%(error_type)s "
    "mode=%(mode)s status=%(status)s hit_count=%(hit_count)s reason=%(reason)s "
    "protocol=%(protocol)s model_response_failure_kind=%(model_response_failure_kind)s"
)

logging.basicConfig(level=logging.INFO, format=STRUCTURED_LOG_FORMAT)


class StructuredLogDefaults(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        defaults: dict[str, str] = {
            "trace_id": "none",
            "timeout_seconds": "none",
            "error_code": "none",
            "error_type": "none",
            "mode": "none",
            "status": "none",
            "hit_count": "none",
            "reason": "none",
            "protocol": "none",
            "model_response_failure_kind": "none",
        }
        for name, value in defaults.items():
            if not hasattr(record, name):
                setattr(record, name, value)
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(StructuredLogDefaults())
    handler.setFormatter(logging.Formatter(STRUCTURED_LOG_FORMAT))

logger = logging.getLogger(__name__)
TRACE_HEADER: Final = "X-Trace-Id"
SAFE_TRACE_ID: Final = re.compile(TRACE_ID_PATTERN)
JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

settings = get_settings()
internal_service_token = settings.require_internal_service_token()
retriever = KnowledgeRetriever(settings)
workflow = AnalysisWorkflow(settings, retriever)
runner = AnalysisRunner(settings, workflow)
internal_authenticator = InternalServiceAuthenticator(
    internal_service_token
)

app = FastAPI(
    title="Support Copilot AI",
    version="0.1.0",
    description="Ticket classification, knowledge retrieval, and grounded reply service.",
)


def request_trace_id(request: Request) -> str:
    return safe_trace_id(request.headers.get(TRACE_HEADER))


def safe_trace_id(candidate: str | None) -> str:
    if candidate is not None and SAFE_TRACE_ID.fullmatch(candidate):
        return candidate
    return f"trace_{uuid4().hex[:12]}"


def error_response(
    status_code: int,
    code: str,
    message: str,
    trace_id: str,
    details: dict[str, JsonValue] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "traceId": trace_id,
            "details": details or {},
        },
        headers={TRACE_HEADER: trace_id},
    )


@app.middleware("http")
async def propagate_trace_id(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    trace_id = request_trace_id(request)
    request.state.trace_id = trace_id
    try:
        response = await call_next(request)
    # Sole HTTP conversion boundary: preserve a stable response without exposing fault details.
    except Exception as exception:  # noqa: BROAD_EXCEPT_OK
        logger.error(
            "request.unhandled_error",
            extra={
                "trace_id": trace_id,
                "error_code": "INTERNAL_SERVER_ERROR",
                "error_type": type(exception).__name__,
            },
        )
        response = error_response(
            500,
            "INTERNAL_SERVER_ERROR",
            "The request could not be completed.",
            trace_id,
        )
    response.headers[TRACE_HEADER] = trace_id
    return response


@app.exception_handler(InternalServiceAuthenticationError)
async def internal_authentication_error(
    request: Request,
    exception: InternalServiceAuthenticationError,
) -> JSONResponse:
    trace_id = request.state.trace_id
    if request.headers.get(TRACE_HEADER) is None:
        trace_id = safe_trace_id(exception.trace_id)
        request.state.trace_id = trace_id
    return error_response(
        401,
        "INTERNAL_SERVICE_AUTHENTICATION_REQUIRED",
        "A valid internal service credential is required.",
        trace_id,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    errors = [
        {
            "type": error["type"],
            "loc": list(error["loc"]),
            "msg": error["msg"],
        }
        for error in exception.errors()
    ]
    return error_response(
        422,
        "REQUEST_VALIDATION_FAILED",
        "Request validation failed.",
        request.state.trace_id,
        {"errors": errors},
    )


@app.exception_handler(KnowledgeReleaseMismatchError)
async def knowledge_release_mismatch_error(
    request: Request,
    _exception: KnowledgeReleaseMismatchError,
) -> JSONResponse:
    return error_response(
        409,
        "KNOWLEDGE_RELEASE_MISMATCH",
        "Requested knowledge release does not match the active corpus.",
        request.state.trace_id,
    )


@app.get("/health")
async def health() -> dict[str, str | bool | int]:
    return {
        "status": "up",
        "service": settings.app_name,
        "mode": settings.effective_mode,
        "liveReady": settings.live_ready,
        "knowledgeChunks": retriever.chunk_count,
    }


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "up"}


@app.get("/health/ready")
async def readiness() -> JSONResponse:
    snapshot = retriever.readiness.snapshot()
    ready = snapshot.provider_ready and snapshot.index_ready
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "up" if ready else "degraded",
            "dependencies": {
                "provider": "up" if snapshot.provider_ready else "degraded",
                "index": "up" if snapshot.index_ready else "degraded",
            },
            "indexReason": snapshot.index_reason,
            "mode": settings.effective_mode,
        },
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    http_request: Request,
    _authenticated: Annotated[
        None,
        Depends(internal_authenticator.require),
    ],
) -> AnalyzeResponse | JSONResponse:
    # FastAPI 会先用 AnalyzeRequest 校验传入 JSON，
    # 工作流返回后再用 AnalyzeResponse 校验响应结构。
    trusted_trace_id = http_request.state.trace_id
    if request.trace_id != trusted_trace_id:
        return error_response(
            400,
            "TRACE_ID_MISMATCH",
            "Body traceId must match X-Trace-Id.",
            trusted_trace_id,
        )
    try:
        return await runner.run(request)
    except AnalysisProcessingTimeoutError as exc:
        logger.error(
            "analysis.processing_timeout",
            extra={
                "trace_id": exc.trace_id,
                "timeout_seconds": exc.timeout_seconds,
            },
        )
        return error_response(
            504,
            "AI_PROCESSING_TIMEOUT",
            "AI analysis exceeded its processing deadline.",
            exc.trace_id,
        )
