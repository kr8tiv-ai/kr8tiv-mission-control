"""Agent model-policy helpers for OpenClaw provisioning."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

_CLI_PROVIDERS = frozenset(
    {"anthropic", "openai-codex", "claude-cli", "codex-cli", "google-gemini-cli"}
)
_API_PROVIDERS = frozenset({"google", "nvidia"})
_PRIMARY_MODEL_ALIASES: dict[str, str] = {
    # Normalize legacy aliases to canonical IDs within the same provider.
    "anthropic/claude-opus-4-6": "claude-cli/claude-opus-4-6",
    "openai-codex/gpt-5-codex": "codex-cli/gpt-5.3-codex",
    "openai-codex/gpt-5.3-codex": "codex-cli/gpt-5.3-codex",
    "google-gemini-cli/gemini-3.1": "google-gemini-cli/gemini-3-pro-preview",
    "google/gemini-3-pro-preview": "google-gemini-cli/gemini-3-pro-preview",
    "nvidia/moonshotai/kimi-k2-5": "nvidia/moonshotai/kimi-k2.5",
}
_FALLBACK_MODEL_ALIASES: dict[str, str] = {
    # Preserve API provider IDs for fallback routes.
    "openai-codex/gpt-5-codex": "openai-codex/gpt-5.3-codex",
    "google-gemini-cli/gemini-3.1": "google/gemini-3-pro-preview",
    "google-gemini-cli/gemini-3-pro-preview": "google/gemini-3-pro-preview",
    "nvidia/moonshotai/kimi-k2-5": "nvidia/moonshotai/kimi-k2.5",
}

_LOCKED_AGENT_MODEL_POLICIES: dict[str, dict[str, Any]] = {
    "friday": {
        "provider": "claude-cli",
        "model": "claude-cli/claude-opus-4-6",
        "fallback_models": ["anthropic/claude-opus-4-6"],
        "transport": "cli",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to Claude Opus 4.6 via Claude CLI backend.",
    },
    "arsenal": {
        "provider": "codex-cli",
        "model": "codex-cli/gpt-5.3-codex",
        "fallback_models": ["openai-codex/gpt-5.3-codex"],
        "transport": "cli",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to Codex 5.3 via Codex CLI backend.",
    },
    "edith": {
        "provider": "google-gemini-cli",
        "model": "google-gemini-cli/gemini-3-pro-preview",
        "fallback_models": ["google/gemini-3-pro-preview"],
        "transport": "cli",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to Gemini 3.1 lane via Gemini CLI backend.",
    },
    "jocasta": {
        "provider": "nvidia",
        "model": "nvidia/moonshotai/kimi-k2.5",
        "fallback_models": [],
        "transport": "api",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to Kimi K2.5 via NVIDIA API (free tier route).",
    },
}


def _normalized_agent_name(name: str | None) -> str:
    return (name or "").strip().lower()


def _as_nonempty_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _infer_provider_from_model(model: str | None) -> str | None:
    if not model or "/" not in model:
        return None
    provider = model.split("/", 1)[0].strip()
    return provider or None


def _infer_transport(provider: str | None) -> str:
    if provider in _CLI_PROVIDERS:
        return "cli"
    if provider in _API_PROVIDERS:
        return "api"
    return "api"


def _normalize_primary_model(model: str | None) -> str | None:
    if model is None:
        return None
    return _PRIMARY_MODEL_ALIASES.get(model, model)


def _normalize_fallback_model(model: str | None) -> str | None:
    if model is None:
        return None
    return _FALLBACK_MODEL_ALIASES.get(model, model)


def _candidate_fallback_values(policy: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("fallback_models", "fallbacks"):
        value = policy.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            candidates.extend(parts)
            continue
        if isinstance(value, (list, tuple, set)):
            candidates.extend(str(item).strip() for item in value if str(item).strip())
    return candidates


def _normalize_fallback_models(*, policy: Mapping[str, Any], primary_model: str) -> list[str]:
    normalized: list[str] = []
    for raw in _candidate_fallback_values(policy):
        candidate = _normalize_fallback_model(_as_nonempty_str(raw))
        if candidate is None or candidate == primary_model or candidate in normalized:
            continue
        normalized.append(candidate)
    return normalized


def locked_model_policy_for_name(name: str | None) -> dict[str, Any] | None:
    policy = _LOCKED_AGENT_MODEL_POLICIES.get(_normalized_agent_name(name))
    if policy is None:
        return None
    return deepcopy(policy)


def normalize_model_policy(policy: object) -> dict[str, Any] | None:
    if not isinstance(policy, Mapping):
        return None

    model = _as_nonempty_str(policy.get("model"))
    if model is not None:
        model = _normalize_primary_model(model)
    inferred_provider = _infer_provider_from_model(model)
    provider = inferred_provider or _as_nonempty_str(policy.get("provider"))
    if model is None:
        return None

    transport = _as_nonempty_str(policy.get("transport"))
    normalized_transport = (transport or _infer_transport(provider)).lower()
    if normalized_transport not in {"cli", "api"}:
        normalized_transport = _infer_transport(provider)

    locked = bool(policy.get("locked"))
    allow_self_change = bool(policy.get("allow_self_change", not locked))

    normalized: dict[str, Any] = {
        "provider": provider or "",
        "model": model,
        "fallback_models": _normalize_fallback_models(policy=policy, primary_model=model),
        "transport": normalized_transport,
        "locked": locked,
        "allow_self_change": allow_self_change,
    }
    notes = _as_nonempty_str(policy.get("notes"))
    if notes:
        normalized["notes"] = notes
    return normalized


def is_model_policy_locked(policy: object) -> bool:
    normalized = normalize_model_policy(policy)
    if normalized is None:
        return False
    return bool(normalized.get("locked")) and not bool(normalized.get("allow_self_change", False))


def resolve_agent_model_policy(*, agent_name: str, requested: object) -> dict[str, Any] | None:
    locked = locked_model_policy_for_name(agent_name)
    if locked is not None:
        return locked
    return normalize_model_policy(requested)


def enforce_agent_model_policy(agent: Any) -> bool:
    desired = resolve_agent_model_policy(
        agent_name=getattr(agent, "name", ""),
        requested=getattr(agent, "model_policy", None),
    )
    current = normalize_model_policy(getattr(agent, "model_policy", None))
    if current == desired:
        return False
    setattr(agent, "model_policy", desired)
    return True


def model_id_for_policy(policy: object) -> str | None:
    normalized = normalize_model_policy(policy)
    if normalized is None:
        return None
    model = normalized.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def provider_for_policy(policy: object) -> str:
    normalized = normalize_model_policy(policy)
    if normalized is None:
        return ""
    provider = normalized.get("provider")
    if isinstance(provider, str):
        return provider
    return ""


def transport_for_policy(policy: object) -> str:
    normalized = normalize_model_policy(policy)
    if normalized is None:
        return ""
    transport = normalized.get("transport")
    if isinstance(transport, str):
        return transport
    return ""


def fallback_models_for_policy(policy: object) -> list[str]:
    normalized = normalize_model_policy(policy)
    if normalized is None:
        return []
    value = normalized.get("fallback_models")
    if not isinstance(value, list):
        return []
    models: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if text and text not in models:
            models.append(text)
    return models
