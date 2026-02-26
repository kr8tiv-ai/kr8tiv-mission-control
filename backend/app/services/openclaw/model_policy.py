"""Agent model-policy helpers for OpenClaw provisioning."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

_CLI_PROVIDERS = frozenset({"openai-codex", "google-gemini-cli"})
_API_PROVIDERS = frozenset({"nvidia"})
_MODEL_ALIASES: dict[str, str] = {
    # Legacy id used in earlier runs; current OpenClaw runtime exposes this as pro-preview.
    "google-gemini-cli/gemini-3.1": "google-gemini-cli/gemini-3-pro-preview",
    # Normalize historical punctuation variant.
    "nvidia/moonshotai/kimi-k2-5": "nvidia/moonshotai/kimi-k2.5",
}

_LOCKED_AGENT_MODEL_POLICIES: dict[str, dict[str, Any]] = {
    "friday": {
        "provider": "openai-codex",
        "model": "openai-codex/gpt-5.3-codex",
        "transport": "cli",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to GPT-5.3 Codex CLI runtime.",
    },
    "arsenal": {
        "provider": "openai-codex",
        "model": "openai-codex/gpt-5.3-codex",
        "transport": "cli",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to GPT-5.3 Codex CLI runtime.",
    },
    "edith": {
        "provider": "google-gemini-cli",
        "model": "google-gemini-cli/gemini-3-pro-preview",
        "transport": "cli",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to Gemini 3 Pro Preview CLI runtime.",
    },
    "jocasta": {
        "provider": "nvidia",
        "model": "nvidia/moonshotai/kimi-k2.5",
        "transport": "api",
        "locked": True,
        "allow_self_change": False,
        "notes": "Pinned to Kimi K2.5 via NVIDIA API.",
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
        model = _MODEL_ALIASES.get(model, model)
    provider = _as_nonempty_str(policy.get("provider")) or _infer_provider_from_model(model)
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
