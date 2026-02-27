"""Application settings and environment configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.auth_mode import AuthMode

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = BACKEND_ROOT / ".env"
LOCAL_AUTH_TOKEN_MIN_LENGTH = 50
LOCAL_AUTH_TOKEN_PLACEHOLDERS = frozenset(
    {
        "change-me",
        "changeme",
        "replace-me",
        "replace-with-strong-random-token",
    },
)


class Settings(BaseSettings):
    """Typed runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        # Load `backend/.env` regardless of current working directory.
        # (Important when running uvicorn from repo root or via a process manager.)
        env_file=[DEFAULT_ENV_FILE, ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/openclaw_agency"

    # Auth mode: "clerk" for Clerk JWT auth, "local" for shared bearer token auth.
    auth_mode: AuthMode
    local_auth_token: str = ""

    # Clerk auth (auth only; roles stored in DB)
    clerk_secret_key: str = ""
    clerk_api_url: str = "https://api.clerk.com"
    clerk_verify_iat: bool = True
    clerk_leeway: float = 10.0

    cors_origins: str = ""
    base_url: str = ""

    # Database lifecycle
    db_auto_migrate: bool = False

    # RQ queueing / dispatch
    rq_redis_url: str = "redis://localhost:6379/0"
    rq_queue_name: str = "default"
    rq_dispatch_throttle_seconds: float = 15.0
    rq_dispatch_max_retries: int = 3
    rq_dispatch_retry_base_seconds: float = 10.0
    rq_dispatch_retry_max_seconds: float = 120.0
    recovery_loop_enabled: bool = True
    recovery_loop_interval_seconds: int = 180

    # Task mode orchestration
    arena_allowed_agents: str = "friday,arsenal,edith,jocasta"
    arena_reviewer_agent: str = "arsenal"
    # Pin to @latest for stability; consider pinning to specific version in production
    notebooklm_runner_cmd: str = "uvx --from notebooklm-mcp-cli@latest nlm"
    notebooklm_profiles_root: str = "/var/lib/notebooklm/profiles"
    notebooklm_timeout_seconds: int = 120
    channel_rollout_phase: str = "phase1"
    enabled_ingress_channels: str = "telegram"
    telegram_owner_user_id: str = ""
    telegram_bot_username: str = ""
    telegram_bot_user_id: str = ""
    telegram_strict_dm_policy: bool = True
    telegram_allow_public_moderation: bool = True
    telegram_require_owner_tag_or_reply: bool = True
    telegram_require_owner_for_task_direction: bool = True

    # Kr8tiv distribution layer
    distribution_cli_command: str = "node kr8tiv-claw/dist/index.js"
    distribution_artifacts_root: str = str(BACKEND_ROOT / "artifacts" / "tenants")

    # Supermemory runtime retrieval
    supermemory_api_key: str = ""
    supermemory_base_url: str = "https://api.supermemory.ai"
    supermemory_top_k: int = 3
    supermemory_threshold: float = 0.45
    supermemory_timeout_seconds: int = 8
    supermemory_container_tag_prefix: str = "tenant"

    # OpenClaw gateway runtime compatibility (security baseline)
    gateway_min_version: str = "2026.2.26"

    # Prompt evolution gate guardrails
    prompt_eval_enabled: bool = True
    prompt_promotion_min_score_delta: float = 0.03
    prompt_promotion_require_non_regression: bool = True
    prompt_optimization_default_budget_usd: float = 5.0

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"
    log_use_utc: bool = False
    request_log_slow_ms: int = Field(default=1000, ge=0)
    request_log_include_health: bool = False

    @model_validator(mode="after")
    def _defaults(self) -> Self:
        if self.auth_mode == AuthMode.CLERK:
            if not self.clerk_secret_key.strip():
                raise ValueError(
                    "CLERK_SECRET_KEY must be set and non-empty when AUTH_MODE=clerk.",
                )
        elif self.auth_mode == AuthMode.LOCAL:
            token = self.local_auth_token.strip()
            if (
                not token
                or len(token) < LOCAL_AUTH_TOKEN_MIN_LENGTH
                or token.lower() in LOCAL_AUTH_TOKEN_PLACEHOLDERS
            ):
                raise ValueError(
                    "LOCAL_AUTH_TOKEN must be at least 50 characters and non-placeholder when AUTH_MODE=local.",
                )
        # In dev, default to applying Alembic migrations at startup to avoid
        # schema drift (e.g. missing newly-added columns).
        if "db_auto_migrate" not in self.model_fields_set and self.environment == "dev":
            self.db_auto_migrate = True
        return self

    def allowed_arena_agent_ids(self) -> tuple[str, ...]:
        """Return normalized arena-eligible agent identifiers from config."""
        values: list[str] = []
        for raw in self.arena_allowed_agents.split(","):
            normalized = raw.strip().lower()
            if normalized and normalized not in values:
                values.append(normalized)
        return tuple(values)

    def ingress_channels(self) -> tuple[str, ...]:
        """Return normalized externally enabled ingress channels."""
        values: list[str] = []
        for raw in self.enabled_ingress_channels.split(","):
            normalized = raw.strip().lower()
            if normalized and normalized not in values:
                values.append(normalized)
        return tuple(values)


settings = Settings()
