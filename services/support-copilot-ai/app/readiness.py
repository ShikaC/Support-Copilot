from dataclasses import dataclass, replace
from threading import Lock


@dataclass(frozen=True, slots=True)
class DependencyReadinessSnapshot:
    provider_ready: bool
    index_ready: bool


@dataclass(frozen=True, slots=True)
class _DependencyStageState:
    embedding_provider_ready: bool
    generation_provider_ready: bool
    index_ready: bool


class RuntimeDependencyReadiness:
    """Stores dependency outcomes shared by async requests and health probes."""

    def __init__(self, provider_ready: bool, index_ready: bool) -> None:
        self._lock = Lock()
        self._state = _DependencyStageState(
            embedding_provider_ready=provider_ready,
            generation_provider_ready=provider_ready,
            index_ready=index_ready,
        )

    def snapshot(self) -> DependencyReadinessSnapshot:
        with self._lock:
            return DependencyReadinessSnapshot(
                provider_ready=(
                    self._state.embedding_provider_ready
                    and self._state.generation_provider_ready
                ),
                index_ready=self._state.index_ready,
            )

    def record_live_retrieval_failure(self) -> None:
        with self._lock:
            self._state = replace(
                self._state,
                embedding_provider_ready=False,
                index_ready=False,
            )

    def record_live_retrieval_success(self) -> None:
        with self._lock:
            self._state = replace(
                self._state,
                embedding_provider_ready=True,
                index_ready=True,
            )

    def record_live_generation_failure(self) -> None:
        with self._lock:
            self._state = replace(self._state, generation_provider_ready=False)

    def record_live_generation_success(self) -> None:
        with self._lock:
            self._state = replace(self._state, generation_provider_ready=True)
