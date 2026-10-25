from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "bookleaf"

    jwt_secret: str  # required: app refuses to start without it
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    cors_origins: str = "http://localhost:5173"

    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-120b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 20

    seed_author_password: str = ""
    seed_admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production(self):
        if self.app_env.lower() == "production":
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if "localhost" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must list the deployed frontend origin in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()