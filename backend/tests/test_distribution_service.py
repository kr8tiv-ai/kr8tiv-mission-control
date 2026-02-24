# ruff: noqa: S101
from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from app.schemas.distribution import DistributionGenerateRequest
from app.services.distribution_service import DistributionService


def _flag_value(command: list[str], flag: str) -> str:
    idx = command.index(flag)
    return command[idx + 1]


def _write_compile_outputs(out_dir: Path, *, tenant_id: str) -> None:
    workspace = out_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    for name in ("AGENTS.md", "SOUL.md", "TOOLS.md", "USER.md", "HEARTBEAT.md"):
        (workspace / name).write_text(f"# {name}\n", encoding="utf-8")
    (out_dir / "openclaw.json").write_text(
        json.dumps({"gateway": {"pairing": {"required": True}}}, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "skill-pack-manifest.json").write_text(
        json.dumps({"installRoot": "<workspace>/skills"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "artifact-metadata.json").write_text(
        json.dumps(
            {
                "tenantId": tenant_id,
                "containerTag": f"tenant:{tenant_id}",
                "workspaceFiles": ["AGENTS.md", "SOUL.md", "TOOLS.md", "USER.md", "HEARTBEAT.md"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_distribution_service_generates_bundle_and_download_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = DistributionService(
        cli_command="node dist/index.js",
        artifacts_root=tmp_path / "artifacts" / "tenants",
    )
    cli_calls: list[list[str]] = []

    def _fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> CompletedProcess[str]:
        del cwd, text, capture_output, check
        cli_calls.append(command)
        if "compile" in command:
            subcommand = "compile"
        elif "compose" in command:
            subcommand = "compose"
        else:
            subcommand = "unknown"
        out_dir = Path(_flag_value(command, "--out"))
        if subcommand == "compile":
            _write_compile_outputs(out_dir, tenant_id=_flag_value(command, "--tenant-id"))
            return CompletedProcess(command, 0, stdout='{"ok":true}\n', stderr="")
        if subcommand == "compose":
            (out_dir / "docker-compose.tenant.yml").write_text(
                "services:\n  openclaw-gateway: {}\n",
                encoding="utf-8",
            )
            return CompletedProcess(command, 0, stdout='{"ok":true}\n', stderr="")
        msg = f"unexpected subcommand: {subcommand}"
        raise AssertionError(msg)

    monkeypatch.setattr("app.services.distribution_service.subprocess.run", _fake_run)

    result = await service.generate_bundle(
        DistributionGenerateRequest(
            tenant_slug="acme-support",
            harness_yaml="tenant:\n  slug: acme-support\n",
            include_watchdog=True,
        )
    )

    assert result.tenant_id.startswith("acme-support-")
    assert result.include_watchdog is True
    assert result.artifact_dir.exists()
    assert (result.artifact_dir / "openclaw.json").exists()
    assert (result.artifact_dir / "docker-compose.tenant.yml").exists()
    assert len(cli_calls) == 2
    assert "--watchdog" in cli_calls[1]

    metadata = service.get_artifact_metadata(result.tenant_id)
    assert metadata.tenant_id == result.tenant_id
    assert "openclaw.json" in metadata.files

    archive_path = service.create_download_archive(result.tenant_id)
    assert archive_path.exists()
    assert archive_path.suffix == ".zip"


def test_distribution_service_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    service = DistributionService(
        cli_command="node dist/index.js",
        artifacts_root=tmp_path / "artifacts" / "tenants",
    )
    with pytest.raises(ValueError):
        service.get_artifact_metadata("../escape")
