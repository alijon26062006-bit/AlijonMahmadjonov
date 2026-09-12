"""Configuration for the analysis service.

Everything is read once at start-up and validated together, so a
misconfigured deployment fails immediately rather than at the first request
that happens to need a missing value — the same contract the Go service has.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
        # Fields with an environment alias must also be settable by their own
        # name. Without this, constructing Settings in code silently falls
        # back to the default and a validation test passes for the wrong
        # reason.
        populate_by_name=True,
    )

    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "info"
    port: int = 8000

    # The shared secret the Go API presents. This service is not public: it
    # sits behind the API and is reachable only from it, and the token is what
    # enforces that if the network ever fails to.
    service_token: str = Field(default="", alias="AI_SERVICE_TOKEN")

    # Model access. Absent in development, and every endpoint degrades to a
    # deterministic answer rather than pretending to have produced one.
    anthropic_api_key: str = Field(default="", alias="AI_API_KEY")
    model: str = Field(default="claude-sonnet-5", alias="AI_MODEL")
    # A long summary costs more and reads worse; these bound both.
    max_output_tokens: int = 1024
    model_timeout_seconds: float = 30.0

    # Bounds on the work a single analysis request may ask for, so one
    # developer with 400 repositories cannot monopolise the service.
    max_repositories: int = 60
    max_readme_chars: int = 8_000
    max_manifest_chars: int = 64_000

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        allowed = {"debug", "info", "warning", "error"}
        lowered = value.lower()
        if lowered not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return lowered

    @property
    def model_configured(self) -> bool:
        """Whether a model is reachable.

        Read at every call site that would otherwise produce a fabricated
        answer. The product shows a configuration state instead.
        """
        return bool(self.anthropic_api_key)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate_for_runtime(self) -> list[str]:
        """Returns the problems that should stop a deployment."""
        problems: list[str] = []
        if self.is_production and not self.service_token:
            problems.append("AI_SERVICE_TOKEN is required in production")
        if self.is_production and len(self.service_token) < 32:
            problems.append("AI_SERVICE_TOKEN must be at least 32 characters in production")
        if self.port < 1 or self.port > 65535:
            problems.append(f"PORT must be between 1 and 65535 (got {self.port})")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
