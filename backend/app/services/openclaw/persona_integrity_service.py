"""Service for persona checksum baselines and drift detection."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Final
from uuid import UUID

from sqlmodel import select

from app.core.time import utcnow
from app.models.agent_persona_integrity import AgentPersonaIntegrity
from app.schemas.persona_integrity import PersonaIntegrityCheckResult, PersonaIntegrityHashes
from app.services.openclaw.db_service import OpenClawDBService

SOUL_FILE: Final[str] = "SOUL.md"
USER_FILE: Final[str] = "USER.md"
IDENTITY_FILE: Final[str] = "IDENTITY.md"
AGENTS_FILE: Final[str] = "AGENTS.md"

_DRIFT_FIELD_MAP: Final[tuple[tuple[str, str], ...]] = (
    ("soul_sha256", SOUL_FILE),
    ("user_sha256", USER_FILE),
    ("identity_sha256", IDENTITY_FILE),
    ("agents_sha256", AGENTS_FILE),
)


def _normalize_content(content: object) -> str:
    if content is None:
        return ""
    text = str(content)
    return text.replace("\r\n", "\n")


def _sha256_text(content: object) -> str:
    normalized = _normalize_content(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _hashes_from_files(file_contents: Mapping[str, object] | None) -> PersonaIntegrityHashes:
    payload = file_contents or {}
    return PersonaIntegrityHashes(
        soul_sha256=_sha256_text(payload.get(SOUL_FILE, "")),
        user_sha256=_sha256_text(payload.get(USER_FILE, "")),
        identity_sha256=_sha256_text(payload.get(IDENTITY_FILE, "")),
        agents_sha256=_sha256_text(payload.get(AGENTS_FILE, "")),
    )


def _drift_fields(
    *,
    baseline: PersonaIntegrityHashes,
    current: PersonaIntegrityHashes,
) -> list[str]:
    changed: list[str] = []
    for attr_name, file_name in _DRIFT_FIELD_MAP:
        if getattr(baseline, attr_name) != getattr(current, attr_name):
            changed.append(file_name)
    return changed


def _hashes_from_row(row: AgentPersonaIntegrity) -> PersonaIntegrityHashes:
    return PersonaIntegrityHashes(
        soul_sha256=row.soul_sha256,
        user_sha256=row.user_sha256,
        identity_sha256=row.identity_sha256,
        agents_sha256=row.agents_sha256,
    )


class PersonaIntegrityService(OpenClawDBService):
    """Persist and evaluate persona integrity checksums for an agent."""

    async def _get_row(self, *, agent_id: UUID) -> AgentPersonaIntegrity | None:
        statement = select(AgentPersonaIntegrity).where(AgentPersonaIntegrity.agent_id == agent_id)
        return (await self.session.exec(statement)).first()

    async def reset_baseline(
        self,
        *,
        agent_id: UUID,
        file_contents: Mapping[str, object] | None,
    ) -> AgentPersonaIntegrity:
        """Replace baseline checksums with the current workspace persona files."""
        now = utcnow()
        hashes = _hashes_from_files(file_contents)
        row = await self._get_row(agent_id=agent_id)
        if row is None:
            row = AgentPersonaIntegrity(
                agent_id=agent_id,
                soul_sha256=hashes.soul_sha256,
                user_sha256=hashes.user_sha256,
                identity_sha256=hashes.identity_sha256,
                agents_sha256=hashes.agents_sha256,
                drift_count=0,
                last_checked_at=now,
                last_drift_at=None,
                last_drift_fields=[],
                created_at=now,
                updated_at=now,
            )
        else:
            row.soul_sha256 = hashes.soul_sha256
            row.user_sha256 = hashes.user_sha256
            row.identity_sha256 = hashes.identity_sha256
            row.agents_sha256 = hashes.agents_sha256
            row.last_checked_at = now
            row.last_drift_at = None
            row.last_drift_fields = []
            row.updated_at = now
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def verify_persona_integrity(
        self,
        *,
        agent_id: UUID,
        file_contents: Mapping[str, object] | None,
    ) -> PersonaIntegrityCheckResult:
        """Check current persona files against stored baseline and record drift metadata."""
        now = utcnow()
        current = _hashes_from_files(file_contents)
        row = await self._get_row(agent_id=agent_id)
        if row is None:
            row = await self.reset_baseline(agent_id=agent_id, file_contents=file_contents)
            baseline = _hashes_from_row(row)
            return PersonaIntegrityCheckResult(
                agent_id=agent_id,
                baseline_created=True,
                drift_detected=False,
                drift_fields=[],
                drift_count=row.drift_count,
                baseline=baseline,
                current=current,
            )

        baseline = _hashes_from_row(row)
        changed_fields = _drift_fields(baseline=baseline, current=current)
        drift_detected = len(changed_fields) > 0
        row.last_checked_at = now
        if drift_detected:
            row.drift_count += 1
            row.last_drift_at = now
            row.last_drift_fields = changed_fields
        else:
            row.last_drift_fields = []
        row.updated_at = now
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return PersonaIntegrityCheckResult(
            agent_id=agent_id,
            baseline_created=False,
            drift_detected=drift_detected,
            drift_fields=changed_fields,
            drift_count=row.drift_count,
            baseline=baseline,
            current=current,
        )
