from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "support-copilot-ai"
    ai_mode: Literal["mock", "live", "auto"] = "mock"
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_base_url: str | None = None
    openai_chat_model: str | None = None
    openai_embedding_model: str | None = None
    openai_timeout_seconds: float = 20.0
    openai_max_retries: int = 2
    retrieval_top_n: int = 10
    retrieval_top_k: int = 3

    @model_validator(mode="after")
    def validate_live_mode(self) -> "Settings":
        if self.ai_mode == "live" and not self.live_ready:
            raise ValueError(
                "AI_MODE=live requires OPENAI_API_KEY, OPENAI_CHAT_MODEL, "
                "and OPENAI_EMBEDDING_MODEL"
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
