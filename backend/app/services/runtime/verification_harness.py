"""Deterministic runtime verification checks for rollout gating."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.time import utcnow
from app.services.notebooklm_capability_gate import evaluate_notebooklm_capability


@dataclass(frozen=True, slots=True)
class VerificationCheckResult:
    """Single verification check outcome."""

    name: str
    required: bool
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class VerificationHarnessResult:
    """Aggregated verification result with required-check failure count."""

    generated_at: datetime
    checks: list[VerificationCheckResult]
    all_passed: bool
    required_failed: int


def _external_probe_urls() -> tuple[str, ...]:
    raw = (os.getenv("VERIFICATION_EXTERNAL_HEALTH_URLS") or "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


async def _probe_external_health(*, urls: tuple[str, ...]) -> tuple[bool, str]:
    failures: list[str] = []
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        for url in urls:
            try:
                response = await client.get(url)
            except Exception:
                failures.append(f"{url}=timeout")
                continue
            if response.status_code >= 400:
                failures.append(f"{url}=status_{response.status_code}")

    if failures:
        return False, f"failed:{';'.join(failures)}"
    return True, f"ok:{len(urls)}"


def _route_check(*, name: str, route_paths: set[str], expected_paths: tuple[str, ...]) -> VerificationCheckResult:
    missing = [path for path in expected_paths if path not in route_paths]
    if missing:
        return VerificationCheckResult(
            name=name,
            required=True,
            passed=False,
            detail=f"missing_routes:{','.join(missing)}",
        )
    return VerificationCheckResult(name=name, required=True, passed=True, detail="ok")


async def run_verification_harness(
    *,
    route_paths: set[str],
    profile: str = "auto",
) -> VerificationHarnessResult:
    """Run deterministic control-plane verification checks."""
    checks: list[VerificationCheckResult] = [
        _route_check(
            name="health_routes",
            route_paths=route_paths,
            expected_paths=("/health", "/readyz"),
        ),
        _route_check(
            name="notebook_gate_route",
            route_paths=route_paths,
            expected_paths=("/api/v1/runtime/notebook/gate",),
        ),
        _route_check(
            name="recovery_run_route",
            route_paths=route_paths,
            expected_paths=("/api/v1/runtime/recovery/run",),
        ),
    ]

    probe_urls = _external_probe_urls()
    if not probe_urls:
        checks.append(
            VerificationCheckResult(
                name="external_health_probe",
                required=False,
                passed=True,
                detail="skipped:unconfigured",
            )
        )
    else:
        probe_passed, probe_detail = await _probe_external_health(urls=probe_urls)
        checks.append(
            VerificationCheckResult(
                name="external_health_probe",
                required=True,
                passed=probe_passed,
                detail=probe_detail,
            )
        )

    gate = await evaluate_notebooklm_capability(profile=profile, require_notebook=False)
    checks.append(
        VerificationCheckResult(
            name="notebook_capability",
            required=True,
            passed=gate.state == "ready",
            detail=f"{gate.state}:{gate.reason}",
        )
    )

    required_failed = sum(1 for check in checks if check.required and not check.passed)
    all_passed = required_failed == 0 and all(check.passed for check in checks)
    return VerificationHarnessResult(
        generated_at=utcnow(),
        checks=checks,
        all_passed=all_passed,
        required_failed=required_failed,
    )
