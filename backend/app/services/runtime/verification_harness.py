"""Deterministic runtime verification checks for rollout gating."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
