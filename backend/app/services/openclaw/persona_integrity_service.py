"""Persona checksum baseline and drift detection service."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from uuid import UUID

from sqlmodel import select

from app.core.time import utcnow
from app.models.agent_persona_integrity import AgentPersonaIntegrity
from app.schemas.persona_integrity import PersonaIntegrityDriftResult
from app.services.openclaw.db_service import OpenClawDBService

_FILE_FIELD_MAP = {
    "SOUL.md": "soul_sha256",
    "USER.md": "user_sha256",
    "IDENTITY.md": "identity_sha256",
    "AGENTS.md": "agents_sha256",
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _checksum_payload(file_contents: Mapping[str, str | None]) -> dict[str, str]:
    payload: dict[str, str] = {}
    for file_name, field_name in _FILE_FIELD_MAP.items():
        raw = file_contents.get(file_name, "")
        payload[field_name] = _sha256_text("" if raw is None else str(raw))
    return payload


class PersonaIntegrityService(OpenClawDBService):
    """Stores baseline persona checksums and reports runtime drift."""

    async def get_baseline(self, agent_id: UUID) -> AgentPersonaIntegrity | None:
        return (
            await self.session.exec(
                select(AgentPersonaIntegrity).where(AgentPersonaIntegrity.agent_id == agent_id),
            )
        ).first()

    async def create_or_update_baseline(
        self,
        *,
        agent_id: UUID,
        file_contents: Mapping[str, str | None],
    ) -> AgentPersonaIntegrity:
        checksums = _checksum_payload(file_contents)
        baseline = await self.get_baseline(agent_id)
        now = utcnow()
        if baseline is None:
            baseline = AgentPersonaIntegrity(
                agent_id=agent_id,
                **checksums,
                last_checked_at=now,
            )
        else:
            baseline.soul_sha256 = checksums["soul_sha256"]
            baseline.user_sha256 = checksums["user_sha256"]
            baseline.identity_sha256 = checksums["identity_sha256"]
            baseline.agents_sha256 = checksums["agents_sha256"]
            baseline.last_checked_at = now
            baseline.updated_at = now
        await self.add_commit_refresh(baseline)
        return baseline

    async def detect_drift(
        self,
        *,
        agent_id: UUID,
        file_contents: Mapping[str, str | None],
    ) -> PersonaIntegrityDriftResult:
        baseline = await self.get_baseline(agent_id)
        if baseline is None:
            msg = f"persona integrity baseline missing for agent {agent_id}"
            raise ValueError(msg)

        checksums = _checksum_payload(file_contents)
        drifted_files: list[str] = []
        for file_name, field_name in _FILE_FIELD_MAP.items():
            if getattr(baseline, field_name) != checksums[field_name]:
                drifted_files.append(file_name)

        now = utcnow()
        baseline.last_checked_at = now
        baseline.updated_at = now
        if drifted_files:
            baseline.last_drift_at = now
            baseline.drift_count += 1
        await self.add_commit_refresh(baseline)

        return PersonaIntegrityDriftResult(
            agent_id=agent_id,
            has_drift=bool(drifted_files),
            drifted_files=drifted_files,
        )
