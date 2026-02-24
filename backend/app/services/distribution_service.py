"""Service layer for kr8tiv-claw tenant distribution bundle generation."""

from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import BACKEND_ROOT, settings
from app.schemas.distribution import (
    DistributionArtifactMetadata,
    DistributionGenerateRequest,
    DistributionGenerateResult,
)

REPO_ROOT = BACKEND_ROOT.parent
_TENANT_ID_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class DistributionService:
    """Generate, inspect, and package per-tenant distribution artifacts."""

    def __init__(
        self,
        *,
        cli_command: str | None = None,
        artifacts_root: Path | None = None,
    ) -> None:
        self._cli_command = (cli_command or settings.distribution_cli_command).strip()
        self._artifacts_root = artifacts_root or Path(settings.distribution_artifacts_root)
        self._artifacts_root.mkdir(parents=True, exist_ok=True)

    def _base_cli_command(self) -> list[str]:
        if not self._cli_command:
            msg = "distribution_cli_command is empty"
            raise ValueError(msg)
        return shlex.split(self._cli_command, posix=(os.name != "nt"))

    @staticmethod
    def _validate_tenant_token(value: str, *, field_name: str) -> str:
        candidate = value.strip().lower()
        if not candidate:
            msg = f"{field_name} is required"
            raise ValueError(msg)
        if "/" in candidate or "\\" in candidate:
            msg = f"{field_name} contains invalid path separators"
            raise ValueError(msg)
        import re

        if not re.match(_TENANT_ID_PATTERN, candidate):
            msg = f"{field_name} must match {_TENANT_ID_PATTERN}"
            raise ValueError(msg)
        return candidate

    def _artifact_dir_for(self, tenant_id: str) -> Path:
        safe_tenant_id = self._validate_tenant_token(tenant_id, field_name="tenant_id")
        artifact_dir = (self._artifacts_root / safe_tenant_id).resolve()
        root_resolved = self._artifacts_root.resolve()
        if root_resolved not in artifact_dir.parents and artifact_dir != root_resolved:
            msg = "tenant_id resolves outside artifacts root"
            raise ValueError(msg)
        return artifact_dir

    def _run_cli(self, args: list[str]) -> None:
        command = [*self._base_cli_command(), *args]
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            detail = stderr or stdout or "unknown cli error"
            msg = f"distribution CLI failed ({' '.join(command)}): {detail}"
            raise RuntimeError(msg)

    @staticmethod
    def _list_files(artifact_dir: Path) -> list[str]:
        return sorted(
            str(path.relative_to(artifact_dir)).replace("\\", "/")
            for path in artifact_dir.rglob("*")
            if path.is_file()
        )

    def _distribution_meta_path(self, artifact_dir: Path) -> Path:
        return artifact_dir / "distribution-metadata.json"

    def _write_distribution_metadata(
        self,
        *,
        artifact_dir: Path,
        tenant_id: str,
        tenant_slug: str,
        include_watchdog: bool,
        created_at: datetime,
    ) -> None:
        payload = {
            "tenant_id": tenant_id,
            "tenant_slug": tenant_slug,
            "include_watchdog": include_watchdog,
            "created_at": created_at.isoformat(),
        }
        self._distribution_meta_path(artifact_dir).write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read_distribution_metadata(self, artifact_dir: Path) -> dict[str, object]:
        path = self._distribution_meta_path(artifact_dir)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        created_at = datetime.fromtimestamp(artifact_dir.stat().st_mtime, tz=UTC).isoformat()
        return {"include_watchdog": False, "created_at": created_at}

    async def generate_bundle(self, request: DistributionGenerateRequest) -> DistributionGenerateResult:
        tenant_slug = self._validate_tenant_token(request.tenant_slug, field_name="tenant_slug")
        tenant_id = f"{tenant_slug}-{secrets.token_hex(4)}"
        created_at = datetime.now(tz=UTC)
        artifact_dir = self._artifact_dir_for(tenant_id)
        artifact_dir.mkdir(parents=True, exist_ok=False)

        harness_path = artifact_dir / "harness.yaml"
        harness_path.write_text(request.harness_yaml.strip() + "\n", encoding="utf-8")

        self._run_cli(
            [
                "compile",
                "--harness",
                str(harness_path),
                "--out",
                str(artifact_dir),
                "--tenant",
                tenant_slug,
                "--tenant-id",
                tenant_id,
            ]
        )

        compose_args = [
            "compose",
            "--harness",
            str(harness_path),
            "--out",
            str(artifact_dir),
            "--tenant",
            tenant_id,
        ]
        if request.include_watchdog:
            compose_args.append("--watchdog")
        self._run_cli(compose_args)
        self._write_distribution_metadata(
            artifact_dir=artifact_dir,
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            include_watchdog=request.include_watchdog,
            created_at=created_at,
        )
        metadata = self.get_artifact_metadata(tenant_id)
        return DistributionGenerateResult(
            tenant_id=metadata.tenant_id,
            tenant_slug=metadata.tenant_slug,
            artifact_dir=metadata.artifact_dir,
            files=metadata.files,
            include_watchdog=request.include_watchdog,
            created_at=metadata.created_at,
        )

    def get_artifact_metadata(self, tenant_id: str) -> DistributionArtifactMetadata:
        artifact_dir = self._artifact_dir_for(tenant_id)
        if not artifact_dir.exists():
            msg = f"artifact not found: {tenant_id}"
            raise FileNotFoundError(msg)
        meta = self._read_distribution_metadata(artifact_dir)
        tenant_slug = str(meta.get("tenant_slug") or tenant_id.rsplit("-", 1)[0])
        include_watchdog = bool(meta.get("include_watchdog", False))
        created_at_raw = str(meta.get("created_at", ""))
        created_at = (
            datetime.fromisoformat(created_at_raw)
            if created_at_raw
            else datetime.fromtimestamp(artifact_dir.stat().st_mtime, tz=UTC)
        )
        return DistributionArtifactMetadata(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            artifact_dir=artifact_dir,
            files=self._list_files(artifact_dir),
            include_watchdog=include_watchdog,
            created_at=created_at,
        )

    def create_download_archive(self, tenant_id: str) -> Path:
        artifact_dir = self._artifact_dir_for(tenant_id)
        if not artifact_dir.exists():
            msg = f"artifact not found: {tenant_id}"
            raise FileNotFoundError(msg)
        archive_file = self._artifacts_root / f"{tenant_id}.zip"
        if archive_file.exists():
            archive_file.unlink()
        archive_path = shutil.make_archive(
            base_name=str(archive_file.with_suffix("")),
            format="zip",
            root_dir=str(artifact_dir),
        )
        return Path(archive_path)
