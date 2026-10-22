from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./bookleaf.db"

    jwt_secret: str  # required: app refuses to start without it
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    cors_origins: str = "http://localhost:5173"

    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    llm_timeout_seconds: int = 20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()