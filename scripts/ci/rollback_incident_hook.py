#!/usr/bin/env python3
"""Create a rollback incident issue for rollout gate failures."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib import error, request


def parse_probe_urls(raw: str) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for chunk in raw.split(","):
        value = chunk.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return tuple(values)


def build_issue_payload(
    *,
    owner: str,
    repo: str,
    run_id: str,
    workflow_name: str,
    gate_status: str,
    status_reason: str,
    probe_urls: tuple[str, ...],
) -> dict[str, Any]:
    run_url = f"https://github.com/{owner}/{repo}/actions/runs/{run_id}"
    probe_lines = "\n".join(f"- `{url}`" for url in probe_urls) if probe_urls else "- `<none>`"
    title = f"[rollout-gate] failure incident run {run_id}"
    body = (
        "Automated rollback hook triggered after rollout gate failure.\n\n"
        f"- Workflow: `{workflow_name}`\n"
        f"- Run: {run_url}\n"
        f"- Gate status: `{gate_status}`\n"
        f"- Status reason: `{status_reason}`\n\n"
        "Configured probe URLs:\n"
        f"{probe_lines}\n\n"
        "Action required:\n"
        "1. Execute rollback runbook.\n"
        "2. Restore last known-good runtime image tags.\n"
        "3. Re-run gate-only validation before next publish.\n"
    )
    return {"title": title, "body": body, "labels": ["incident", "rollout-gate"]}


def create_issue(
    *,
    token: str,
    owner: str,
    repo: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub issue create failed ({exc.code}): {detail}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create rollout gate failure incident issue")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "unknown"))
    parser.add_argument("--workflow-name", default=os.getenv("GITHUB_WORKFLOW", "unknown"))
    parser.add_argument("--gate-status", default="failed")
    parser.add_argument("--status-reason", default="probe_failures")
    parser.add_argument("--probe-urls", default=os.getenv("RUNTIME_HEALTH_URLS", ""))
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
    if not token and not args.dry_run:
        raise RuntimeError("GITHUB_TOKEN or GH_TOKEN is required.")

    payload = build_issue_payload(
        owner=str(args.owner),
        repo=str(args.repo),
        run_id=str(args.run_id),
        workflow_name=str(args.workflow_name),
        gate_status=str(args.gate_status),
        status_reason=str(args.status_reason),
        probe_urls=parse_probe_urls(str(args.probe_urls)),
    )

    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    issue = create_issue(
        token=token,
        owner=str(args.owner),
        repo=str(args.repo),
        payload=payload,
    )
    print(
        json.dumps(
            {
                "issue_number": issue.get("number"),
                "issue_url": issue.get("html_url"),
                "created": bool(issue),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
