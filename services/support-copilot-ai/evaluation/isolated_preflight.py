"""Offline artifact and effective non-secret configuration check. No provider calls."""
from app.config import Settings
from app.embedding_artifact import EmbeddingArtifactStore
from app.knowledge_source import load_knowledge_corpus
from pydantic import BaseModel


class Preflight(BaseModel):
    mode: str
    model: str | None
    embedding_model: str | None
    protocol: str
    chat_base_url: str | None
    embedding_base_url: str | None
    sdk_seconds: float
    python_seconds: float
    configured_sdk_retries: int
    artifact_id: str
    rows: int
    dimension: int


def main() -> None:
    settings = Settings()
    corpus = load_knowledge_corpus(settings.knowledge_path)
    artifact = EmbeddingArtifactStore(settings, corpus).load_active()
    print(Preflight(mode=settings.effective_mode, model=settings.openai_chat_model,
        embedding_model=settings.openai_embedding_model, protocol=settings.openai_chat_protocol,
        chat_base_url=settings.openai_base_url, embedding_base_url=settings.embedding_base_url,
        sdk_seconds=settings.openai_timeout_seconds, python_seconds=settings.ai_processing_timeout_seconds, configured_sdk_retries=settings.openai_max_retries,
        artifact_id=artifact.manifest.artifact_id, rows=artifact.manifest.row_count,
        dimension=artifact.manifest.vector_dimension).model_dump_json())


if __name__ == "__main__":
    main()
