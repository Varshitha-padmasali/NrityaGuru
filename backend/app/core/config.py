"""Application configuration loaded from environment variables / .env."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NrityaGuru Knowledge & Tutor API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "testing", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # SecretStr hides the value in repr()/logs. Use .get_secret_value() to read it.
    gemini_api_key: SecretStr | None = None
    reference_review_token: SecretStr | None = None
    reference_reviewer_identity: str | None = None
    nrityaguru_hand_task: str | None = None
    nrityaguru_mlp_bundle: str | None = None
    evaluation_runtime_verified: bool = False
    # Verified Oct 2026: Google recommends gemini-3.8-flash for new projects. gemini-2.5-flash
    # still exists but access is limited to existing users since 18 Sep 2026.
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    # Optional. Valid: LOW, MEDIUM, HIGH. (MINIMAL is rejected by gemini-3.8-flash.)
    # Leave unset to use the model default (MEDIUM).
    gemini_thinking_level: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    database_url: SecretStr | None = None

    # Requests per minute per client IP for the tutor endpoint (it calls a paid API).
    tutor_rate_limit_per_minute: int = Field(default=20, ge=1, le=600)
    max_video_upload_mb: int = Field(default=100, ge=1, le=100)
    max_video_duration_seconds: int = Field(default=45, ge=1, le=180)
    max_video_decoded_frames: int = Field(default=5000, ge=1, le=20000)
    max_video_frame_pixels: int = Field(default=1920 * 1080, ge=4096, le=3840 * 2160)

    # Development only: serve clearly-labelled MOCK evaluation results until the real
    # evaluation module is connected. Must be false in production.
    use_mock_evaluation: bool = False

    # Browser origins allowed to call this API (comma separated). The Next.js dev server runs on
    # http://localhost:3000. Add the real frontend URL for deployment.
    cors_allow_origins: str = "http://localhost:3000"

    # When False, API callers cannot request records without supporting sources.
    # Source-cited and verified records remain available and visibly labelled.
    allow_unverified_records: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value())

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url and self.database_url.get_secret_value())

    @property
    def reference_review_configured(self) -> bool:
        return bool(self.reference_review_token and self.reference_review_token.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
