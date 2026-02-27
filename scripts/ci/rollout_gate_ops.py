#!/usr/bin/env python3
"""Operator utility for rollout gate secret updates and gate-only validation dispatch."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib import error, parse, request


DEFAULT_OWNER = "kr8tiv-ai"
DEFAULT_REPO = "kr8tiv-mission-control"
DEFAULT_WORKFLOW = "publish-mission-control-images.yml"
DEFAULT_BRANCH = "main"


class ActionsApiProtocol(Protocol):
    def set_secret(self, name: str, value: str) -> None:
        ...

    def dispatch_publish_workflow(self, *, gate_only: bool, allow_skipped_gate: bool) -> int | None:
        ...


@dataclass(frozen=True, slots=True)
class RolloutOpsConfig:
    health_urls: tuple[str, ...]
    rollback_command: str
    update_rollback: bool
    dispatch_gate_only: bool
    allow_skipped_gate: bool


def parse_health_urls(raw_values: list[str]) -> tuple[str, ...]:
    """Normalize comma/newline separated URLs and validate protocols."""
    urls: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        for chunk in raw.split(","):
            value = chunk.strip()
            if not value:
                continue
            if not (value.startswith("http://") or value.startswith("https://")):
                raise ValueError(f"Health URL must use http/https: {value}")
            if value in seen:
                continue
            seen.add(value)
            urls.append(value)
    if not urls:
        raise ValueError("At least one health URL is required.")
    return tuple(urls)


def read_health_urls_file(path: str) -> list[str]:
    data = Path(path).read_text(encoding="utf-8")
    return [line.strip() for line in data.splitlines() if line.strip()]


def _resolve_github_token() -> str:
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value

    # Fallback to git credential manager if env token is not set.
    credential_query = "protocol=https\nhost=github.com\n\n"
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input=credential_query,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("Unable to execute git credential helper for GitHub token lookup.") from exc

    if result.returncode != 0:
        raise RuntimeError(
            "GitHub token not found in env and git credential lookup failed. "
            "Set GH_TOKEN or GITHUB_TOKEN."
        )

    for line in result.stdout.splitlines():
        if line.startswith("password="):
            token = line.split("=", 1)[1].strip()
            if token:
                return token

    raise RuntimeError("GitHub token not found in env or git credential manager.")


def _encrypt_secret_for_github(value: str, public_key_b64: str) -> str:
    try:
        from nacl import encoding, public
    except Exception as exc:  # pragma: no cover - dependency is expected in operator env
        raise RuntimeError(
            "PyNaCl is required to encrypt GitHub Actions secrets. Install with: pip install pynacl"
        ) from exc

    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoder=encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(value.encode("utf-8"))
    return encoding.Base64Encoder.encode(encrypted).decode("utf-8")


class GitHubActionsApi:
    def __init__(
        self,
        *,
        owner: str,
        repo: str,
        token: str,
        workflow: str,
        branch: str,
        poll_seconds: int,
        poll_timeout_seconds: int,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.workflow = workflow
        self.branch = branch
        self.poll_seconds = max(2, poll_seconds)
        self.poll_timeout_seconds = max(10, poll_timeout_seconds)
        self._base = f"https://api.github.com/repos/{owner}/{repo}"
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=self._headers, method=method)
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                with request.urlopen(req, timeout=30) as response:  # noqa: S310
                    raw = response.read().decode("utf-8").strip()
                    if not raw:
                        return None
                    return json.loads(raw)
            except error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code in {502, 503, 504} and attempt < 4:
                    last_exc = RuntimeError(f"GitHub API transient error {exc.code}: {detail}")
                    time.sleep(float(attempt * 2))
                    continue
                raise RuntimeError(f"GitHub API error {exc.code}: {detail}") from exc
            except (error.URLError, TimeoutError) as exc:
                last_exc = exc
                if attempt < 4:
                    time.sleep(float(attempt * 2))
                    continue
                raise RuntimeError(f"GitHub API network error: {exc}") from exc
        if last_exc is not None:  # pragma: no cover - defensive completion path
            raise RuntimeError(f"GitHub API request failed after retries: {last_exc}")
        raise RuntimeError("GitHub API request failed without explicit exception.")

    def set_secret(self, name: str, value: str) -> None:
        key_url = f"{self._base}/actions/secrets/public-key"
        key_payload = self._request("GET", key_url)
        key_id = str(key_payload["key_id"])
        key_b64 = str(key_payload["key"])

        encrypted = _encrypt_secret_for_github(value, key_b64)
        secret_url = f"{self._base}/actions/secrets/{name}"
        payload = {"encrypted_value": encrypted, "key_id": key_id}
        self._request("PUT", secret_url, payload=payload)

    def _latest_dispatch_run(self) -> dict[str, Any] | None:
        query = parse.urlencode({"event": "workflow_dispatch", "branch": self.branch, "per_page": 5})
        runs_url = f"{self._base}/actions/workflows/{self.workflow}/runs?{query}"
        payload = self._request("GET", runs_url)
        runs = payload.get("workflow_runs", [])
        if not runs:
            return None
        return runs[0]

    def _dispatch_runs(self) -> list[dict[str, Any]]:
        query = parse.urlencode({"event": "workflow_dispatch", "branch": self.branch, "per_page": 10})
        runs_url = f"{self._base}/actions/workflows/{self.workflow}/runs?{query}"
        payload = self._request("GET", runs_url)
        return list(payload.get("workflow_runs", []))

    def _run_by_id(self, run_id: int) -> dict[str, Any]:
        run_url = f"{self._base}/actions/runs/{run_id}"
        payload = self._request("GET", run_url)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Invalid run payload for run_id={run_id}")
        return payload

    def dispatch_publish_workflow(self, *, gate_only: bool, allow_skipped_gate: bool) -> int | None:
        previous = self._latest_dispatch_run()
        previous_run_id = parse_run_id(previous) if previous else None

        dispatch_url = f"{self._base}/actions/workflows/{self.workflow}/dispatches"
        dispatch_payload = {
            "ref": self.branch,
            "inputs": {
                "gate_only": str(gate_only).lower(),
                "allow_skipped_gate": str(allow_skipped_gate).lower(),
            },
        }
        dispatched_at = time.time()
        self._request("POST", dispatch_url, payload=dispatch_payload)

        deadline = time.time() + self.poll_timeout_seconds
        target_run_id: int | None = None
        while time.time() < deadline:
            runs = self._dispatch_runs()
            target_run_id = select_new_run_id(
                runs,
                previous_run_id=previous_run_id,
                not_before_epoch=dispatched_at - 2.0,
            )
            if target_run_id is not None:
                break
            time.sleep(self.poll_seconds)

        if target_run_id is None:
            return None

        while time.time() < deadline:
            run_payload = self._run_by_id(target_run_id)
            if str(run_payload.get("status")) == "completed":
                return target_run_id
            time.sleep(self.poll_seconds)
        return target_run_id


def parse_run_id(run: dict[str, Any] | None) -> int | None:
    if run is None:
        return None
    run_id = run.get("id")
    if isinstance(run_id, int):
        return run_id
    if isinstance(run_id, str) and run_id.isdigit():
        return int(run_id)
    return None


def parse_run_created_epoch(run: dict[str, Any]) -> float | None:
    created_at = str(run.get("created_at", "")).strip()
    if not created_at:
        return None
    try:
        normalized = created_at.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def select_new_run_id(
    runs: list[dict[str, Any]],
    *,
    previous_run_id: int | None,
    not_before_epoch: float | None = None,
) -> int | None:
    for run in runs:
        run_id = parse_run_id(run)
        if run_id is None:
            continue
        if previous_run_id is not None and run_id == previous_run_id:
            continue
        if not_before_epoch is not None:
            created_epoch = parse_run_created_epoch(run)
            if created_epoch is None or created_epoch < not_before_epoch:
                continue
        return run_id
    return None


def execute_config(config: RolloutOpsConfig, api: ActionsApiProtocol) -> dict[str, Any]:
    health_urls_value = ",".join(config.health_urls)
    api.set_secret("RUNTIME_HEALTH_URLS", health_urls_value)

    rollback_updated = False
    if config.update_rollback:
        rollback_command = config.rollback_command.strip()
        if not rollback_command:
            raise ValueError("Rollback command is required when --update-rollback is set.")
        api.set_secret("RUNTIME_ROLLBACK_COMMAND", rollback_command)
        rollback_updated = True

    run_id: int | None = None
    if config.dispatch_gate_only:
        run_id = api.dispatch_publish_workflow(
            gate_only=True,
            allow_skipped_gate=config.allow_skipped_gate,
        )

    return {
        "health_urls_count": len(config.health_urls),
        "health_secret_updated": True,
        "rollback_updated": rollback_updated,
        "dispatch_run_id": run_id,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update rollout gate secrets and optionally run gate-only dispatch."
    )
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="GitHub org/user owner")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository name")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow file name")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch ref for workflow dispatch")
    parser.add_argument(
        "--health-urls",
        action="append",
        default=[],
        help="Health URL input (comma-separated supported). Use multiple times as needed.",
    )
    parser.add_argument(
        "--health-urls-file",
        default="",
        help="Optional file with one health URL per line (or comma-separated lines).",
    )
    parser.add_argument(
        "--update-rollback",
        action="store_true",
        help="Update RUNTIME_ROLLBACK_COMMAND secret.",
    )
    parser.add_argument("--rollback-command", default="", help="Rollback command string")
    parser.add_argument(
        "--dispatch-gate-only",
        action="store_true",
        help="Dispatch publish workflow in gate-only mode after secret updates.",
    )
    parser.add_argument(
        "--allow-skipped-gate",
        action="store_true",
        help="Set workflow input allow_skipped_gate=true on dispatch.",
    )
    parser.add_argument("--poll-seconds", type=int, default=10, help="Dispatch polling interval")
    parser.add_argument(
        "--poll-timeout-seconds",
        type=int,
        default=300,
        help="Dispatch completion polling timeout",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved config without writing secrets or dispatching workflow.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    raw_health_inputs = list(args.health_urls)
    if args.health_urls_file:
        raw_health_inputs.extend(read_health_urls_file(args.health_urls_file))
    health_urls = parse_health_urls(raw_health_inputs)
    config = RolloutOpsConfig(
        health_urls=health_urls,
        rollback_command=str(args.rollback_command),
        update_rollback=bool(args.update_rollback),
        dispatch_gate_only=bool(args.dispatch_gate_only),
        allow_skipped_gate=bool(args.allow_skipped_gate),
    )

    if args.dry_run:
        payload = {
            "owner": args.owner,
            "repo": args.repo,
            "workflow": args.workflow,
            "branch": args.branch,
            "health_urls_count": len(config.health_urls),
            "update_rollback": config.update_rollback,
            "dispatch_gate_only": config.dispatch_gate_only,
            "allow_skipped_gate": config.allow_skipped_gate,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    token = _resolve_github_token()
    api = GitHubActionsApi(
        owner=str(args.owner),
        repo=str(args.repo),
        token=token,
        workflow=str(args.workflow),
        branch=str(args.branch),
        poll_seconds=int(args.poll_seconds),
        poll_timeout_seconds=int(args.poll_timeout_seconds),
    )
    result = execute_config(config, api)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
