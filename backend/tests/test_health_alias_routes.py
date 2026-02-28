# ruff: noqa: S101
from __future__ import annotations

from app.main import app


def test_versioned_health_alias_route_registered() -> None:
    paths = {str(route.path) for route in app.routes if hasattr(route, "path")}
    assert "/health" in paths
    assert "/healthz" in paths
    assert "/api/v1/health" in paths

