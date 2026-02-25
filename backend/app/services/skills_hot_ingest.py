"""Skill hot-ingestion validation and quarantine workflow."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_ALLOWED_RISK_TIERS = {"low", "medium", "high", "critical"}


@dataclass(frozen=True)
class SkillIngestResult:
    status: str
    metadata: dict[str, object]
    normalized_skill: dict[str, object]
    errors: list[str]


def ingest_skill(payload: dict[str, Any]) -> SkillIngestResult:
    """Validate and normalize one skill payload for runtime routing."""
    name = str(payload.get("name", "")).strip()
    risk_tier = str(payload.get("risk_tier", "medium")).strip().lower()
    source_url = str(payload.get("source_url", "")).strip()

    errors: list[str] = []
    if not name:
        errors.append("name is required")
    if risk_tier not in _ALLOWED_RISK_TIERS:
        errors.append(f"unsupported risk_tier: {risk_tier}")

    normalized_skill: dict[str, object] = {
        "name": name,
        "risk_tier": risk_tier,
        "source_url": source_url,
        "version": str(payload.get("version", "v1")),
    }
    digest_source = json.dumps(normalized_skill, sort_keys=True, ensure_ascii=True).encode("utf-8")
    checksum = hashlib.sha256(digest_source).hexdigest()

    status = "accepted" if not errors else "quarantined"
    metadata: dict[str, object] = {
        "ingest_status": status,
        "ingest_errors": errors,
        "ingest_checksum": checksum,
        "ingested_at": datetime.now(UTC).isoformat(),
        "ingest_version": normalized_skill["version"],
    }

    return SkillIngestResult(
        status=status,
        metadata=metadata,
        normalized_skill=normalized_skill,
        errors=errors,
    )
