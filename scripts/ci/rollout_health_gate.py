#!/usr/bin/env python3
"""Runtime rollout health gate with optional rollback hook.

This script is intentionally stdlib-only so it can run in CI without extra deps.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib import error, request


ProbeFn = Callable[[str, float], dict[str, Any]]
SleepFn = Callable[[float], None]
RunCommandFn = Callable[[str, int], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class GateConfig:
    urls: tuple[str, ...]
    attempts: int = 6
    timeout_seconds: float = 5.0
    sleep_seconds: float = 15.0
    rollback_on_fail: bool = False
    rollback_command: str = ""
    rollback_timeout_seconds: int = 180


def parse_urls(raw: str) -> tuple[str, ...]:
    """Parse comma-separated URLs into a normalized deduplicated tuple."""
    values: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        url = part.strip()
        if not url or url in seen:
            continue
        values.append(url)
        seen.add(url)
    return tuple(values)


def probe_url(url: str, timeout_seconds: float) -> dict[str, Any]:
    """Probe a URL once and return structured result."""
    started = time.monotonic()
    status_code: int | None = None
    ok = False
    detail = "unknown"
    try:
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            status_code = int(response.getcode())
            ok = 200 <= status_code < 400
            detail = "ok" if ok else f"status_{status_code}"
    except error.HTTPError as exc:
        status_code = int(exc.code)
        ok = False
        detail = f"status_{status_code}"
    except Exception as exc:  # pragma: no cover - defensive catch for runtime network errors
        ok = False
        detail = f"error:{type(exc).__name__}"

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "ok": ok,
        "status_code": status_code,
        "detail": detail,
        "elapsed_ms": elapsed_ms,
    }


def run_rollback_command(command: str, timeout_seconds: int) -> dict[str, Any]:
    """Execute rollback command and capture result."""
    try:
        completed = subprocess.run(
            command,
            shell=True,  # noqa: S602 - intentional, command is operator-provided.
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "attempted": True,
            "command": command,
            "timeout_seconds": timeout_seconds,
            "exit_code": completed.returncode,
            "succeeded": completed.returncode == 0,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {
            "attempted": True,
            "command": command,
            "timeout_seconds": timeout_seconds,
            "exit_code": None,
            "succeeded": False,
            "stdout": "",
            "stderr": f"timeout_after_{timeout_seconds}s",
        }


def run_health_gate(
    config: GateConfig,
    *,
    probe_fn: ProbeFn = probe_url,
    sleep_fn: SleepFn = time.sleep,
    run_command_fn: RunCommandFn = run_rollback_command,
) -> dict[str, Any]:
    """Evaluate rollout health and optionally trigger rollback."""
    checked_at = datetime.now(UTC).isoformat()
    rollback: dict[str, Any] = {
        "attempted": False,
        "succeeded": None,
        "exit_code": None,
        "command": config.rollback_command,
    }
    attempts_payload: list[dict[str, Any]] = []

    if not config.urls:
        return {
            "status": "skipped",
            "status_reason": "no_urls_configured",
            "checked_at": checked_at,
            "urls": [],
            "attempts": attempts_payload,
            "failed_urls": [],
            "rollback": rollback,
        }

    final_failed_urls: list[str] = []
    passed = False
    for attempt_idx in range(1, max(1, config.attempts) + 1):
        per_url: list[dict[str, Any]] = []
        failed_urls: list[str] = []
        for url in config.urls:
            probe_result = probe_fn(url, config.timeout_seconds)
            row = {
                "url": url,
                "ok": bool(probe_result.get("ok")),
                "status_code": probe_result.get("status_code"),
                "detail": str(probe_result.get("detail", "")),
                "elapsed_ms": int(probe_result.get("elapsed_ms", 0)),
            }
            per_url.append(row)
            if not row["ok"]:
                failed_urls.append(url)

        all_ok = len(failed_urls) == 0
        attempts_payload.append(
            {
                "attempt": attempt_idx,
                "all_ok": all_ok,
                "results": per_url,
            }
        )
        if all_ok:
            passed = True
            final_failed_urls = []
            break

        final_failed_urls = failed_urls
        if attempt_idx < config.attempts:
            sleep_fn(config.sleep_seconds)

    status = "passed" if passed else "failed"
    status_reason = "all_probes_healthy" if passed else "probe_failures"

    if status == "failed" and config.rollback_on_fail:
        if config.rollback_command.strip():
            rollback = run_command_fn(config.rollback_command, config.rollback_timeout_seconds)
        else:
            rollback = {
                "attempted": False,
                "succeeded": False,
                "exit_code": None,
                "command": "",
                "stderr": "rollback_requested_but_command_missing",
            }

    return {
        "status": status,
        "status_reason": status_reason,
        "checked_at": checked_at,
        "urls": list(config.urls),
        "attempts": attempts_payload,
        "failed_urls": final_failed_urls,
        "rollback": rollback,
    }


def to_env_lines(payload: dict[str, Any]) -> list[str]:
    """Convert gate payload into GitHub-actions friendly key=value lines."""
    rollback = payload.get("rollback", {})
    attempted = bool(rollback.get("attempted"))
    succeeded = rollback.get("succeeded")
    if succeeded is None:
        succeeded_str = "unknown"
    else:
        succeeded_str = "true" if bool(succeeded) else "false"

    lines = [
        f"ROLLOUT_GATE_STATUS={payload.get('status', 'unknown')}",
        f"ROLLOUT_GATE_STATUS_REASON={payload.get('status_reason', '')}",
        f"ROLLOUT_GATE_FAILED_URL_COUNT={len(payload.get('failed_urls', []))}",
        f"ROLLOUT_GATE_ROLLBACK_ATTEMPTED={'true' if attempted else 'false'}",
        f"ROLLOUT_GATE_ROLLBACK_SUCCEEDED={succeeded_str}",
        f"ROLLOUT_GATE_ROLLBACK_EXIT_CODE={rollback.get('exit_code', '')}",
        f"ROLLOUT_GATE_ATTEMPT_COUNT={len(payload.get('attempts', []))}",
    ]
    return lines


def compute_exit_code(status: str, *, fail_on_skipped: bool) -> int:
    """Map gate status to process exit code."""
    if status == "failed":
        return 1
    if status == "skipped" and fail_on_skipped:
        return 1
    return 0


def _write_text(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runtime rollout health gate")
    parser.add_argument("--urls", default="", help="Comma-separated health URLs to probe")
    parser.add_argument("--attempts", type=int, default=6, help="Probe attempts before fail")
    parser.add_argument("--timeout-seconds", type=float, default=5.0, help="Per-request timeout")
    parser.add_argument("--sleep-seconds", type=float, default=15.0, help="Delay between attempts")
    parser.add_argument("--rollback-on-fail", action="store_true", help="Run rollback command when gate fails")
    parser.add_argument("--rollback-command", default="", help="Rollback command")
    parser.add_argument(
        "--rollback-timeout-seconds",
        type=int,
        default=180,
        help="Rollback command timeout",
    )
    parser.add_argument("--evidence-file", default="", help="Optional JSON evidence output path")
    parser.add_argument("--env-file", default="", help="Optional env-style output path")
    parser.add_argument(
        "--fail-on-skipped",
        action="store_true",
        help="Treat skipped gate status as failure",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = GateConfig(
        urls=parse_urls(args.urls),
        attempts=max(1, int(args.attempts)),
        timeout_seconds=max(0.1, float(args.timeout_seconds)),
        sleep_seconds=max(0.0, float(args.sleep_seconds)),
        rollback_on_fail=bool(args.rollback_on_fail),
        rollback_command=str(args.rollback_command),
        rollback_timeout_seconds=max(1, int(args.rollback_timeout_seconds)),
    )

    payload = run_health_gate(config)
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.evidence_file:
        _write_text(args.evidence_file, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.env_file:
        _write_text(args.env_file, "\n".join(to_env_lines(payload)) + "\n")

    return compute_exit_code(str(payload["status"]), fail_on_skipped=bool(args.fail_on_skipped))


if __name__ == "__main__":
    raise SystemExit(main())
