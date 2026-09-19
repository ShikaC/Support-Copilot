import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Final, TypedDict
from uuid import UUID, uuid4

import anyio
from anyio.abc import TaskGroup
from fastapi import Depends, FastAPI, Request
from fastapi import Path as ApiPath
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.analysis_runner import AnalysisProcessingTimeoutError, AnalysisRunner
from app.config import get_settings
from app.embedding_artifact import EmbeddingArtifactError, EmbeddingArtifactStore
from app.index_rebuild import IndexRebuildManager
from app.index_rebuild_models import RebuildError, RebuildRequest, RebuildStatus
from app.internal_auth import (
    InternalServiceAuthenticationError,
    InternalServiceAuthenticator,
)
from app.knowledge import KnowledgeReleaseMismatchError, KnowledgeRetriever
from app.knowledge_source import KnowledgeSourceInvalidError
from app.models import TRACE_ID_PATTERN, AnalyzeRequest, AnalyzeResponse
from app.observability import (
    STRUCTURED_LOG_FORMAT as STRUCTURED_LOG_FORMAT,
)
from app.observability import (
    StructuredLogDefaults as StructuredLogDefaults,
)
from app.observability import (
    configure_structured_logging,
)
from app.workflow import AnalysisWorkflow

configure_structured_logging()

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


@dataclass(frozen=True, slots=True)
class RebuildRuntime:
    manager: IndexRebuildManager
    task_group: TaskGroup


class LifespanState(TypedDict):
    index_rebuild: RebuildRuntime


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[LifespanState]:
    # A graceful shutdown drains accepted builds; no detached worker can outlive its lock.
    async with anyio.create_task_group() as task_group:
        yield {"index_rebuild": RebuildRuntime(IndexRebuildManager(settings), task_group)}


app = FastAPI(
    title="Support Copilot AI",
    version="0.1.0",
    description="Ticket classification, knowledge retrieval, and grounded reply service.",
    lifespan=lifespan,
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
    errors: list[JsonValue] = [
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


@app.exception_handler(RebuildError)
async def rebuild_error(request: Request, exception: RebuildError) -> JSONResponse:
    return error_response(
        exception.status_code,
        exception.code,
        exception.message,
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


def index_version_payload(artifact_store: EmbeddingArtifactStore) -> dict[str, object]:
    inventory = artifact_store.list_artifacts()
    return {
        "activeArtifactId": inventory.active_artifact_id,
        "previousArtifactId": inventory.previous_artifact_id,
        "unreadable": list(inventory.unreadable),
        "versions": [
            {
                "artifactId": item.artifact_id,
                "releaseId": item.release_id,
                "releaseVersion": item.release_version,
                "corpusChecksum": item.corpus_checksum,
                "chunkingVersion": item.chunking_version,
                "embeddingModel": item.embedding_model,
                "vectorDimension": item.vector_dimension,
                "rowCount": item.row_count,
                "documentCount": item.document_count,
                "active": item.active,
                "previous": item.previous,
                "modifiedAt": item.modified_at,
            }
            for item in inventory.artifacts
        ],
    }


@app.get("/knowledge/index/versions")
async def list_index_versions(
    _authenticated: Annotated[
        None,
        Depends(internal_authenticator.require),
    ],
) -> JSONResponse:
    """列出磁盘索引版本与进程语料身份；准备好匹配产物后可显式重载。"""
    corpus = retriever.corpus_metadata
    payload = index_version_payload(retriever.artifact_store)
    payload["corpus"] = {
        "releaseId": corpus.release_id,
        "releaseVersion": corpus.release_version,
        "corpusChecksum": corpus.corpus_checksum,
        "chunkCount": corpus.chunk_count,
    }
    return JSONResponse(content=payload)


@app.post("/knowledge/index/rebuild", response_model=RebuildStatus, status_code=202)
async def rebuild_index(
    body: RebuildRequest,
    request: Request,
    response: Response,
    _authenticated: Annotated[None, Depends(internal_authenticator.require)],
) -> RebuildStatus | JSONResponse:
    """Accept a bounded build of the configured disk corpus without activating it."""
    if not settings.knowledge_index_mutation_enabled:
        return error_response(
            403,
            "INDEX_MUTATION_DISABLED",
            "Index mutation is disabled by configuration.",
            request.state.trace_id,
        )
    runtime: RebuildRuntime = request.state.index_rebuild
    task = await runtime.manager.start(body, request.state.trace_id, runtime.task_group)
    response.headers["Location"] = f"/knowledge/index/rebuild/{task.task_id}"
    return task


@app.get("/knowledge/index/rebuild/{taskId}", response_model=RebuildStatus)
async def get_index_rebuild(
    task_id: Annotated[UUID, ApiPath(alias="taskId")],
    request: Request,
    _authenticated: Annotated[None, Depends(internal_authenticator.require)],
) -> RebuildStatus:
    """Keep completed or failed build evidence readable even when mutation is disabled."""
    runtime: RebuildRuntime = request.state.index_rebuild
    return await runtime.manager.get(task_id)


@app.post("/knowledge/index/reload")
async def reload_index(
    http_request: Request,
    _authenticated: Annotated[
        None,
        Depends(internal_authenticator.require),
    ],
) -> JSONResponse:
    """重新加载语料与向量索引，让切片切换不需要重启进程。

    前提：运维已经先准备好新的语料文件与对应的 artifact，并把 active 指针指过去。
    换切片就是换语料，两者必须一起换；只换一半会在校验里失败并保留旧状态。
    默认关闭：重载会立刻改变线上检索结果，必须由 KNOWLEDGE_INDEX_MUTATION_ENABLED 打开。
    """
    trace_id = http_request.state.trace_id
    if not settings.knowledge_index_mutation_enabled:
        return error_response(
            403,
            "INDEX_MUTATION_DISABLED",
            "Index mutation is disabled by configuration.",
            trace_id,
        )
    try:
        corpus = await retriever.reload_index()
    except KnowledgeSourceInvalidError:
        return error_response(
            409,
            "INDEX_CORPUS_UNRELOADABLE",
            "Knowledge corpus could not be reloaded; check its format and provenance.",
            trace_id,
        )
    except EmbeddingArtifactError as exc:
        return error_response(
            409,
            "INDEX_VERSION_UNUSABLE",
            f"Active index version does not match the corpus: {exc.reason}",
            trace_id,
        )
    except KnowledgeReleaseMismatchError:
        return error_response(
            409,
            "INDEX_RELEASE_MISMATCH",
            "Knowledge corpus provenance does not match its release.",
            trace_id,
        )
    payload = index_version_payload(retriever.artifact_store)
    payload["corpus"] = {
        "releaseId": corpus.release_id,
        "releaseVersion": corpus.release_version,
        "corpusChecksum": corpus.corpus_checksum,
        "chunkCount": corpus.chunk_count,
    }
    return JSONResponse(content=payload)
