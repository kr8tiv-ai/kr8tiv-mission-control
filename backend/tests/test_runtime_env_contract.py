# ruff: noqa: INP001
"""Runtime env contract checks for auth and Telegram ingress gating."""

from __future__ import annotations

from pathlib import Path


def test_backend_env_example_includes_required_auth_and_telegram_keys() -> None:
    env_example = Path(__file__).resolve().parents[2] / "backend" / ".env.example"
    content = env_example.read_text(encoding="utf-8")

    required = (
        "AUTH_MODE=",
        "LOCAL_AUTH_TOKEN=",
        "TELEGRAM_OWNER_USER_ID=",
        "TELEGRAM_BOT_USERNAME=",
        "TELEGRAM_BOT_USER_ID=",
        "TELEGRAM_STRICT_DM_POLICY=",
        "TELEGRAM_REQUIRE_OWNER_TAG_OR_REPLY=",
    )
    for key in required:
        assert key in content


def test_compose_wires_auth_contract_to_backend_frontend_and_worker() -> None:
    compose_file = Path(__file__).resolve().parents[2] / "compose.yml"
    content = compose_file.read_text(encoding="utf-8")

    required_snippets = (
        "AUTH_MODE: ${AUTH_MODE}",
        "LOCAL_AUTH_TOKEN: ${LOCAL_AUTH_TOKEN}",
        "NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}",
        "NEXT_PUBLIC_AUTH_MODE: ${AUTH_MODE}",
    )
    for snippet in required_snippets:
        assert snippet in content
