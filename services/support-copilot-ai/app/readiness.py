from dataclasses import dataclass, replace
from threading import Lock


@dataclass(frozen=True, slots=True)
class DependencyReadinessSnapshot:
    provider_ready: bool
    index_ready: bool
    index_reason: str | None


@dataclass(frozen=True, slots=True)
class _DependencyStageState:
    embedding_provider_ready: bool
    generation_provider_ready: bool
    index_ready: bool
    index_reason: str | None


class RuntimeDependencyReadiness:
    """Stores dependency outcomes shared by async requests and health probes."""

    def __init__(
        self,
        provider_ready: bool,
        index_ready: bool,
        index_reason: str | None = None,
    ) -> None:
        self._lock = Lock()
        self._state = _DependencyStageState(
            embedding_provider_ready=provider_ready,
            generation_provider_ready=provider_ready,
            index_ready=index_ready,
            index_reason=index_reason,
        )

    def snapshot(self) -> DependencyReadinessSnapshot:
        with self._lock:
            return DependencyReadinessSnapshot(
                provider_ready=(
                    self._state.embedding_provider_ready
                    and self._state.generation_provider_ready
                ),
                index_ready=self._state.index_ready,
                index_reason=self._state.index_reason,
            )

    def record_live_retrieval_failure(self) -> None:
        with self._lock:
            self._state = replace(
                self._state,
                embedding_provider_ready=False,
                index_ready=False,
                index_reason="embedding-provider-failure",
            )

    def record_live_retrieval_success(self) -> None:
        with self._lock:
            self._state = replace(
                self._state,
                embedding_provider_ready=True,
                index_ready=True,
                index_reason=None,
            )

    def record_index_failure(self, reason: str) -> None:
        with self._lock:
            self._state = replace(
                self._state,
                index_ready=False,
                index_reason=reason,
            )

    def record_live_generation_failure(self) -> None:
        with self._lock:
            self._state = replace(self._state, generation_provider_ready=False)

    def record_live_generation_success(self) -> None:
        with self._lock:
            self._state = replace(self._state, generation_provider_ready=True)
