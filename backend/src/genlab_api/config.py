from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENLAB_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "development"
    secret_key: str = "development-secret-change-me-please-32chars"
    database_url: str = "sqlite:///./data/genlab.db"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:5173"
    data_dir: Path = Path("./data")
    max_upload_mb: int = 512
    test_size: float = 0.25
    random_state: int = 42
    lease_ttl_seconds: int = 86400
    api_prefix: str = "/api/v1"
    app_name: str = "GenLab M5GP API"
    app_version: str = "1.0.0"
    release_channel: str = "stable"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    def prepare(self) -> None:
        # Convert the configured storage directory to an absolute path once,
        # before API workers change their current working directory.
        self.data_dir = self.data_dir.expanduser().resolve()
        for path in (
            self.data_dir,
            self.upload_dir,
            self.artifact_dir,
            self.log_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.prepare()
    return settings
