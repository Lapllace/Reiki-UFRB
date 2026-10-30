"""Configuração central via pydantic-settings. Nenhum segredo no código."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "local" (padrão), "development", "production"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://reiki:reiki_dev_pass@localhost:5432/reiki"

    # Origens CORS explícitas, separadas por vírgula.
    cors_origins: str = "http://localhost:3000"

    session_cookie_name: str = "reiki_session"
    session_ttl_minutes: int = 60 * 24  # 24 h
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # "lax" | "strict" | "none"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
