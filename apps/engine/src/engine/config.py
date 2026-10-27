from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/engine/config.py -> engine -> src -> apps/engine -> apps -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Optional so the package imports (and tests run) without a .env, e.g. in CI.
    database_url: str | None = None
    football_data_token: str | None = None

    @property
    def sqlalchemy_url(self) -> str:
        """DATABASE_URL with the psycopg (v3) driver, as SQLAlchemy expects."""
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not set; add it to the repo-root .env")
        for prefix in ("postgresql://", "postgres://"):
            if self.database_url.startswith(prefix):
                return "postgresql+psycopg://" + self.database_url.removeprefix(prefix)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
