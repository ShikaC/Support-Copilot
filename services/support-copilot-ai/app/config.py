from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_KNOWLEDGE_PATH: Final = Path(__file__).parent / "data" / "knowledge.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "support-copilot-ai"
    ai_mode: Literal["mock", "live", "auto"] = "mock"
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_base_url: str | None = None
    openai_chat_model: str | None = None
    openai_embedding_model: str | None = None
    openai_timeout_seconds: float = Field(default=20.0, gt=0)
    openai_max_retries: int = Field(default=1, ge=0)
    ai_processing_timeout_seconds: float = Field(default=90.0, gt=0)
    knowledge_path: Path = DEFAULT_KNOWLEDGE_PATH
    knowledge_provenance_path: Path | None = None
    retrieval_top_n: int = 10
    retrieval_top_k: int = 3
    # The local scorer uses a different scale from live cosine similarity.
    mock_retrieval_min_score: float = Field(default=0.25, ge=0, le=1)
    # InMemoryVectorStore returns cosine similarity; results below this value
    # are treated as insufficient evidence instead of being sent to generation.
    live_retrieval_min_score: float = Field(default=0.35, ge=-1, le=1)

    @field_validator("openai_max_retries")
    @classmethod
    def validate_openai_max_retries(cls, value: int) -> int:
        if value > 1:
            raise PydanticCustomError(
                "retry_budget_exceeded",
                "OPENAI_MAX_RETRIES must be between 0 and 1",
            )
        return value

    @model_validator(mode="after")
    def validate_live_mode(self) -> "Settings":
        if self.ai_mode == "live" and not self.live_ready:
            raise PydanticCustomError(
                "live_configuration_incomplete",
                "AI_MODE=live requires OPENAI_API_KEY, OPENAI_CHAT_MODEL, "
                "and OPENAI_EMBEDDING_MODEL",
            )
        return self

    @property
    def live_ready(self) -> bool:
        return bool(
            self.openai_api_key
            and self.openai_chat_model
            and self.openai_embedding_model
        )

    @property
    def effective_mode(self) -> Literal["mock", "live"]:
        if self.ai_mode == "live":
            return "live"
        if self.ai_mode == "auto" and self.live_ready:
            return "live"
        return "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
