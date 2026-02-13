"""Skills marketplace and skill pack APIs."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.gateway_installed_skills import GatewayInstalledSkill
from app.models.gateways import Gateway
from app.models.marketplace_skills import MarketplaceSkill
from app.models.skill_packs import SkillPack
from app.schemas.common import OkResponse
from app.schemas.skills_marketplace import (
    MarketplaceSkillActionResponse,
    MarketplaceSkillCardRead,
    MarketplaceSkillCreate,
    MarketplaceSkillRead,
    SkillPackCreate,
    SkillPackRead,
    SkillPackSyncResponse,
)
from app.services.openclaw.gateway_dispatch import GatewayDispatchService
from app.services.openclaw.gateway_resolver import gateway_client_config, require_gateway_workspace_root
from app.services.openclaw.gateway_rpc import OpenClawGatewayError
from app.services.openclaw.shared import GatewayAgentIdentity
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/skills", tags=["skills"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)
GATEWAY_ID_QUERY = Query(...)


@dataclass(frozen=True)
class PackSkillCandidate:
    """Single skill discovered in a pack repository."""

    name: str
    description: str | None
    source_url: str
    category: str | None = None
    risk: str | None = None
    source: str | None = None


def _skills_install_dir(workspace_root: str) -> str:
    normalized = workspace_root.rstrip("/\\")
    if not normalized:
        return "skills"
    return f"{normalized}/skills"


def _infer_skill_name(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    candidate = path.rsplit("/", maxsplit=1)[-1] if path else parsed.netloc
    candidate = unquote(candidate).removesuffix(".git").replace("-", " ").replace("_", " ")
    if candidate.strip():
        return candidate.strip()
    return "Skill"


def _infer_skill_description(skill_file: Path) -> str | None:
    try:
        content = skill_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    lines = [line.strip() for line in content.splitlines()]
    if not lines:
        return None

    in_frontmatter = False
    for line in lines:
        if line == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            if line.lower().startswith("description:"):
                value = line.split(":", maxsplit=1)[-1].strip().strip('"\'')
                return value or None
            continue
        if not line or line.startswith("#"):
            continue
        return line

    return None


def _infer_skill_display_name(skill_file: Path, fallback: str) -> str:
    try:
        content = skill_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        content = ""

    in_frontmatter = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter and line.lower().startswith("name:"):
            value = line.split(":", maxsplit=1)[-1].strip().strip('"\'')
            if value:
                return value

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if heading:
                return heading

    normalized_fallback = fallback.replace("-", " ").replace("_", " ").strip()
    return normalized_fallback or "Skill"


def _normalize_repo_source_url(source_url: str) -> str:
    normalized = source_url.strip().rstrip("/")
    if normalized.endswith(".git"):
        return normalized[: -len(".git")]
    return normalized


def _to_tree_source_url(repo_source_url: str, branch: str, rel_path: str) -> str:
    repo_url = _normalize_repo_source_url(repo_source_url)
    safe_branch = branch.strip() or "main"
    rel = rel_path.strip().lstrip("/")
    if not rel:
        return f"{repo_url}/tree/{safe_branch}"
    return f"{repo_url}/tree/{safe_branch}/{rel}"


def _repo_base_from_tree_source_url(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    marker = "/tree/"
    marker_index = parsed.path.find(marker)
    if marker_index <= 0:
        return None

    repo_path = parsed.path[:marker_index]
    if not repo_path:
        return None
    return _normalize_repo_source_url(f"{parsed.scheme}://{parsed.netloc}{repo_path}")


def _build_skill_count_by_repo(skills: list[MarketplaceSkill]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for skill in skills:
        repo_base = _repo_base_from_tree_source_url(skill.source_url)
        if repo_base is None:
            continue
        counts[repo_base] = counts.get(repo_base, 0) + 1
    return counts


def _normalize_repo_path(path_value: str) -> str:
    cleaned = path_value.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/").rstrip("/")

    lowered = cleaned.lower()
    if lowered.endswith("/skill.md"):
        cleaned = cleaned.rsplit("/", maxsplit=1)[0]
    elif lowered == "skill.md":
        cleaned = ""

    return cleaned


def _coerce_index_entries(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]

    if isinstance(payload, dict):
        entries = payload.get("skills")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]

    return []


def _collect_pack_skills_from_index(
    *,
    repo_dir: Path,
    source_url: str,
    branch: str,
) -> list[PackSkillCandidate] | None:
    index_file = repo_dir / "skills_index.json"
    if not index_file.is_file():
        return None

    try:
        payload = json.loads(index_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError("unable to read skills_index.json") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("skills_index.json is not valid JSON") from exc

    found: dict[str, PackSkillCandidate] = {}
    for entry in _coerce_index_entries(payload):
        indexed_path = entry.get("path")
        has_indexed_path = False
        rel_path = ""
        if isinstance(indexed_path, str) and indexed_path.strip():
            has_indexed_path = True
            rel_path = _normalize_repo_path(indexed_path)

        indexed_source = entry.get("source_url")
        candidate_source_url: str | None = None
        if isinstance(indexed_source, str) and indexed_source.strip():
            source_candidate = indexed_source.strip()
            if source_candidate.startswith(("https://", "http://")):
                candidate_source_url = source_candidate
            else:
                indexed_rel = _normalize_repo_path(source_candidate)
                if indexed_rel:
                    candidate_source_url = _to_tree_source_url(source_url, branch, indexed_rel)
        elif has_indexed_path:
            candidate_source_url = _to_tree_source_url(source_url, branch, rel_path)

        if not candidate_source_url:
            continue

        indexed_name = entry.get("name")
        if isinstance(indexed_name, str) and indexed_name.strip():
            name = indexed_name.strip()
        else:
            fallback = Path(rel_path).name if rel_path else "Skill"
            name = _infer_skill_name(fallback)

        indexed_description = entry.get("description")
        description = (
            indexed_description.strip()
            if isinstance(indexed_description, str) and indexed_description.strip()
            else None
        )
        indexed_category = entry.get("category")
        category = (
            indexed_category.strip()
            if isinstance(indexed_category, str) and indexed_category.strip()
            else None
        )
        indexed_risk = entry.get("risk")
        risk = (
            indexed_risk.strip()
            if isinstance(indexed_risk, str) and indexed_risk.strip()
            else None
        )
        indexed_source_label = entry.get("source")
        source_label = (
            indexed_source_label.strip()
            if isinstance(indexed_source_label, str) and indexed_source_label.strip()
            else None
        )

        found[candidate_source_url] = PackSkillCandidate(
            name=name,
            description=description,
            source_url=candidate_source_url,
            category=category,
            risk=risk,
            source=source_label,
        )

    return list(found.values())


def _collect_pack_skills_from_repo(
    *,
    repo_dir: Path,
    source_url: str,
    branch: str,
) -> list[PackSkillCandidate]:
    indexed = _collect_pack_skills_from_index(
        repo_dir=repo_dir,
        source_url=source_url,
        branch=branch,
    )
    if indexed is not None:
        return indexed

    found: dict[str, PackSkillCandidate] = {}
    for skill_file in sorted(repo_dir.rglob("SKILL.md")):
        rel_file_parts = skill_file.relative_to(repo_dir).parts
        # Skip hidden folders like .git, .github, etc.
        if any(part.startswith(".") for part in rel_file_parts):
            continue

        skill_dir = skill_file.parent
        rel_dir = (
            ""
            if skill_dir == repo_dir
            else skill_dir.relative_to(repo_dir).as_posix()
        )
        fallback_name = (
            _infer_skill_name(source_url) if skill_dir == repo_dir else skill_dir.name
        )
        name = _infer_skill_display_name(skill_file, fallback=fallback_name)
        description = _infer_skill_description(skill_file)
        tree_url = _to_tree_source_url(source_url, branch, rel_dir)
        found[tree_url] = PackSkillCandidate(
            name=name,
            description=description,
            source_url=tree_url,
        )

    if found:
        return list(found.values())

    return []


def _collect_pack_skills(source_url: str) -> list[PackSkillCandidate]:
    """Clone a pack repository and collect skills from index or `skills/**/SKILL.md`."""
    with TemporaryDirectory(prefix="skill-pack-sync-") as tmp_dir:
        repo_dir = Path(tmp_dir)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", source_url, str(repo_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("git binary not available on the server") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            detail = stderr or "unable to clone pack repository"
            raise RuntimeError(detail) from exc

        try:
            branch = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", "--abbrev-ref", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            branch = "main"

        return _collect_pack_skills_from_repo(
            repo_dir=repo_dir,
            source_url=source_url,
            branch=branch,
        )


def _install_instruction(*, skill: MarketplaceSkill, gateway: Gateway) -> str:
    install_dir = _skills_install_dir(gateway.workspace_root)
    return (
        "MISSION CONTROL SKILL INSTALL REQUEST\n"
        f"Skill name: {skill.name}\n"
        f"Skill source URL: {skill.source_url}\n"
        f"Install destination: {install_dir}\n\n"
        "Actions:\n"
        "1. Ensure the install destination exists.\n"
        "2. Install or update the skill from the source URL into the destination.\n"
        "3. Verify the skill is discoverable by the runtime.\n"
        "4. Reply with success or failure details."
    )


def _uninstall_instruction(*, skill: MarketplaceSkill, gateway: Gateway) -> str:
    install_dir = _skills_install_dir(gateway.workspace_root)
    return (
        "MISSION CONTROL SKILL UNINSTALL REQUEST\n"
        f"Skill name: {skill.name}\n"
        f"Skill source URL: {skill.source_url}\n"
        f"Install destination: {install_dir}\n\n"
        "Actions:\n"
        "1. Remove the skill assets previously installed from this source URL.\n"
        "2. Ensure the skill is no longer discoverable by the runtime.\n"
        "3. Reply with success or failure details."
    )


def _as_card(
    *,
    skill: MarketplaceSkill,
    installation: GatewayInstalledSkill | None,
) -> MarketplaceSkillCardRead:
    return MarketplaceSkillCardRead(
        id=skill.id,
        organization_id=skill.organization_id,
        name=skill.name,
        description=skill.description,
        category=skill.category,
        risk=skill.risk,
        source=skill.source,
        source_url=skill.source_url,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
        installed=installation is not None,
        installed_at=installation.created_at if installation is not None else None,
    )


def _as_skill_pack_read(pack: SkillPack) -> SkillPackRead:
    return SkillPackRead(
        id=pack.id,
        organization_id=pack.organization_id,
        name=pack.name,
        description=pack.description,
        source_url=pack.source_url,
        skill_count=0,
        created_at=pack.created_at,
        updated_at=pack.updated_at,
    )


def _pack_skill_count(*, pack: SkillPack, count_by_repo: dict[str, int]) -> int:
    repo_base = _normalize_repo_source_url(pack.source_url)
    return count_by_repo.get(repo_base, 0)


async def _require_gateway_for_org(
    *,
    gateway_id: UUID,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> Gateway:
    gateway = await Gateway.objects.by_id(gateway_id).first(session)
    if gateway is None or gateway.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gateway not found",
        )
    return gateway


async def _require_marketplace_skill_for_org(
    *,
    skill_id: UUID,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> MarketplaceSkill:
    skill = await MarketplaceSkill.objects.by_id(skill_id).first(session)
    if skill is None or skill.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace skill not found",
        )
    return skill


async def _require_skill_pack_for_org(
    *,
    pack_id: UUID,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> SkillPack:
    pack = await SkillPack.objects.by_id(pack_id).first(session)
    if pack is None or pack.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill pack not found",
        )
    return pack


async def _dispatch_gateway_instruction(
    *,
    session: AsyncSession,
    gateway: Gateway,
    message: str,
) -> None:
    dispatch = GatewayDispatchService(session)
    config = gateway_client_config(gateway)
    session_key = GatewayAgentIdentity.session_key(gateway)
    await dispatch.send_agent_message(
        session_key=session_key,
        config=config,
        agent_name="Gateway Agent",
        message=message,
        deliver=True,
    )


@router.get("/marketplace", response_model=list[MarketplaceSkillCardRead])
async def list_marketplace_skills(
    gateway_id: UUID = GATEWAY_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[MarketplaceSkillCardRead]:
    """List marketplace cards for an org and annotate install state for a gateway."""
    gateway = await _require_gateway_for_org(gateway_id=gateway_id, session=session, ctx=ctx)
    skills = (
        await MarketplaceSkill.objects.filter_by(organization_id=ctx.organization.id)
        .order_by(col(MarketplaceSkill.created_at).desc())
        .all(session)
    )
    installations = await GatewayInstalledSkill.objects.filter_by(gateway_id=gateway.id).all(session)
    installed_by_skill_id = {record.skill_id: record for record in installations}
    return [
        _as_card(skill=skill, installation=installed_by_skill_id.get(skill.id))
        for skill in skills
    ]


@router.post("/marketplace", response_model=MarketplaceSkillRead)
async def create_marketplace_skill(
    payload: MarketplaceSkillCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> MarketplaceSkill:
    """Register or update a direct marketplace skill URL in the catalog."""
    source_url = str(payload.source_url).strip()
    existing = await MarketplaceSkill.objects.filter_by(
        organization_id=ctx.organization.id,
        source_url=source_url,
    ).first(session)
    if existing is not None:
        changed = False
        if payload.name and existing.name != payload.name:
            existing.name = payload.name
            changed = True
        if payload.description is not None and existing.description != payload.description:
            existing.description = payload.description
            changed = True
        if changed:
            existing.updated_at = utcnow()
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
        return existing

    skill = MarketplaceSkill(
        organization_id=ctx.organization.id,
        source_url=source_url,
        name=payload.name or _infer_skill_name(source_url),
        description=payload.description,
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return skill


@router.delete("/marketplace/{skill_id}", response_model=OkResponse)
async def delete_marketplace_skill(
    skill_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> OkResponse:
    """Delete a marketplace catalog entry and any install records that reference it."""
    skill = await _require_marketplace_skill_for_org(skill_id=skill_id, session=session, ctx=ctx)
    installations = await GatewayInstalledSkill.objects.filter_by(skill_id=skill.id).all(session)
    for installation in installations:
        await session.delete(installation)
    await session.delete(skill)
    await session.commit()
    return OkResponse()


@router.post(
    "/marketplace/{skill_id}/install",
    response_model=MarketplaceSkillActionResponse,
)
async def install_marketplace_skill(
    skill_id: UUID,
    gateway_id: UUID = GATEWAY_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> MarketplaceSkillActionResponse:
    """Install a marketplace skill by dispatching instructions to the gateway agent."""
    gateway = await _require_gateway_for_org(gateway_id=gateway_id, session=session, ctx=ctx)
    require_gateway_workspace_root(gateway)
    skill = await _require_marketplace_skill_for_org(skill_id=skill_id, session=session, ctx=ctx)
    try:
        await _dispatch_gateway_instruction(
            session=session,
            gateway=gateway,
            message=_install_instruction(skill=skill, gateway=gateway),
        )
    except OpenClawGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    installation = await GatewayInstalledSkill.objects.filter_by(
        gateway_id=gateway.id,
        skill_id=skill.id,
    ).first(session)
    if installation is None:
        session.add(
            GatewayInstalledSkill(
                gateway_id=gateway.id,
                skill_id=skill.id,
            ),
        )
    else:
        installation.updated_at = utcnow()
        session.add(installation)
    await session.commit()
    return MarketplaceSkillActionResponse(
        skill_id=skill.id,
        gateway_id=gateway.id,
        installed=True,
    )


@router.post(
    "/marketplace/{skill_id}/uninstall",
    response_model=MarketplaceSkillActionResponse,
)
async def uninstall_marketplace_skill(
    skill_id: UUID,
    gateway_id: UUID = GATEWAY_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> MarketplaceSkillActionResponse:
    """Uninstall a marketplace skill by dispatching instructions to the gateway agent."""
    gateway = await _require_gateway_for_org(gateway_id=gateway_id, session=session, ctx=ctx)
    require_gateway_workspace_root(gateway)
    skill = await _require_marketplace_skill_for_org(skill_id=skill_id, session=session, ctx=ctx)
    try:
        await _dispatch_gateway_instruction(
            session=session,
            gateway=gateway,
            message=_uninstall_instruction(skill=skill, gateway=gateway),
        )
    except OpenClawGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    installation = await GatewayInstalledSkill.objects.filter_by(
        gateway_id=gateway.id,
        skill_id=skill.id,
    ).first(session)
    if installation is not None:
        await session.delete(installation)
        await session.commit()
    return MarketplaceSkillActionResponse(
        skill_id=skill.id,
        gateway_id=gateway.id,
        installed=False,
    )


@router.get("/packs", response_model=list[SkillPackRead])
async def list_skill_packs(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[SkillPackRead]:
    """List skill packs configured for the organization."""
    packs = (
        await SkillPack.objects.filter_by(organization_id=ctx.organization.id)
        .order_by(col(SkillPack.created_at).desc())
        .all(session)
    )
    marketplace_skills = await MarketplaceSkill.objects.filter_by(
        organization_id=ctx.organization.id,
    ).all(session)
    count_by_repo = _build_skill_count_by_repo(marketplace_skills)
    return [
        _as_skill_pack_read(pack).model_copy(
            update={"skill_count": _pack_skill_count(pack=pack, count_by_repo=count_by_repo)},
        )
        for pack in packs
    ]


@router.get("/packs/{pack_id}", response_model=SkillPackRead)
async def get_skill_pack(
    pack_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SkillPackRead:
    """Get one skill pack by ID."""
    pack = await _require_skill_pack_for_org(pack_id=pack_id, session=session, ctx=ctx)
    marketplace_skills = await MarketplaceSkill.objects.filter_by(
        organization_id=ctx.organization.id,
    ).all(session)
    count_by_repo = _build_skill_count_by_repo(marketplace_skills)
    return _as_skill_pack_read(pack).model_copy(
        update={"skill_count": _pack_skill_count(pack=pack, count_by_repo=count_by_repo)},
    )


@router.post("/packs", response_model=SkillPackRead)
async def create_skill_pack(
    payload: SkillPackCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SkillPackRead:
    """Register a new skill pack source URL."""
    source_url = str(payload.source_url).strip()
    existing = await SkillPack.objects.filter_by(
        organization_id=ctx.organization.id,
        source_url=source_url,
    ).first(session)
    if existing is not None:
        changed = False
        if payload.name and existing.name != payload.name:
            existing.name = payload.name
            changed = True
        if payload.description is not None and existing.description != payload.description:
            existing.description = payload.description
            changed = True
        if changed:
            existing.updated_at = utcnow()
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
        return _as_skill_pack_read(existing)

    pack = SkillPack(
        organization_id=ctx.organization.id,
        source_url=source_url,
        name=payload.name or _infer_skill_name(source_url),
        description=payload.description,
    )
    session.add(pack)
    await session.commit()
    await session.refresh(pack)
    marketplace_skills = await MarketplaceSkill.objects.filter_by(
        organization_id=ctx.organization.id,
    ).all(session)
    count_by_repo = _build_skill_count_by_repo(marketplace_skills)
    return _as_skill_pack_read(pack).model_copy(
        update={"skill_count": _pack_skill_count(pack=pack, count_by_repo=count_by_repo)},
    )


@router.patch("/packs/{pack_id}", response_model=SkillPackRead)
async def update_skill_pack(
    pack_id: UUID,
    payload: SkillPackCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SkillPackRead:
    """Update a skill pack URL and metadata."""
    pack = await _require_skill_pack_for_org(pack_id=pack_id, session=session, ctx=ctx)
    source_url = str(payload.source_url).strip()

    duplicate = await SkillPack.objects.filter_by(
        organization_id=ctx.organization.id,
        source_url=source_url,
    ).first(session)
    if duplicate is not None and duplicate.id != pack.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pack with this source URL already exists",
        )

    pack.source_url = source_url
    pack.name = payload.name or _infer_skill_name(source_url)
    pack.description = payload.description
    pack.updated_at = utcnow()
    session.add(pack)
    await session.commit()
    await session.refresh(pack)
    marketplace_skills = await MarketplaceSkill.objects.filter_by(
        organization_id=ctx.organization.id,
    ).all(session)
    count_by_repo = _build_skill_count_by_repo(marketplace_skills)
    return _as_skill_pack_read(pack).model_copy(
        update={"skill_count": _pack_skill_count(pack=pack, count_by_repo=count_by_repo)},
    )


@router.delete("/packs/{pack_id}", response_model=OkResponse)
async def delete_skill_pack(
    pack_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> OkResponse:
    """Delete one pack source from the organization."""
    pack = await _require_skill_pack_for_org(pack_id=pack_id, session=session, ctx=ctx)
    await session.delete(pack)
    await session.commit()
    return OkResponse()


@router.post("/packs/{pack_id}/sync", response_model=SkillPackSyncResponse)
async def sync_skill_pack(
    pack_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SkillPackSyncResponse:
    """Clone a pack repository and upsert discovered skills from `skills/**/SKILL.md`."""
    pack = await _require_skill_pack_for_org(pack_id=pack_id, session=session, ctx=ctx)

    try:
        discovered = _collect_pack_skills(pack.source_url)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    existing_skills = await MarketplaceSkill.objects.filter_by(
        organization_id=ctx.organization.id,
    ).all(session)
    existing_by_source = {skill.source_url: skill for skill in existing_skills}

    created = 0
    updated = 0
    for candidate in discovered:
        existing = existing_by_source.get(candidate.source_url)
        if existing is None:
            session.add(
                MarketplaceSkill(
                    organization_id=ctx.organization.id,
                    source_url=candidate.source_url,
                    name=candidate.name,
                    description=candidate.description,
                    category=candidate.category,
                    risk=candidate.risk,
                    source=candidate.source,
                ),
            )
            created += 1
            continue

        changed = False
        if existing.name != candidate.name:
            existing.name = candidate.name
            changed = True
        if existing.description != candidate.description:
            existing.description = candidate.description
            changed = True
        if existing.category != candidate.category:
            existing.category = candidate.category
            changed = True
        if existing.risk != candidate.risk:
            existing.risk = candidate.risk
            changed = True
        if existing.source != candidate.source:
            existing.source = candidate.source
            changed = True

        if changed:
            existing.updated_at = utcnow()
            session.add(existing)
            updated += 1

    await session.commit()

    return SkillPackSyncResponse(
        pack_id=pack.id,
        synced=len(discovered),
        created=created,
        updated=updated,
    )
