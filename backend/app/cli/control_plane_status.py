"""CLI for fetching unified runtime control-plane status."""

from __future__ import annotations

import argparse
import json
import sys
from typing import cast
from urllib import error, parse, request


def build_status_url(
    *,
    base_url: str,
    board_id: str | None,
    profile: str,
    legacy: bool = False,
) -> str:
    """Build the control-plane status endpoint URL with query parameters."""
    normalized_base = base_url.rstrip("/")
    endpoint = (
        f"{normalized_base}/api/v1/runtime/ops/control-plane-status"
        if legacy
        else f"{normalized_base}/api/v1/runtime/control-plane/status"
    )
    query: dict[str, str] = {}
    if board_id:
        query["board_id"] = board_id
    query["profile"] = profile
    return f"{endpoint}?{parse.urlencode(query)}"


def fetch_control_plane_status(
    *,
    base_url: str,
    token: str,
    board_id: str | None,
    profile: str,
    timeout_seconds: int,
) -> dict[str, object]:
    """Fetch status from the backend runtime endpoint."""
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    urls = [
        build_status_url(base_url=base_url, board_id=board_id, profile=profile, legacy=False),
        build_status_url(base_url=base_url, board_id=board_id, profile=profile, legacy=True),
    ]
    last_error: Exception | None = None
    for url in urls:
        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
                payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            if exc.code == 404:
                last_error = exc
                continue
            raise
        decoded = json.loads(payload)
        if not isinstance(decoded, dict):
            msg = "control-plane-status payload is not a JSON object"
            raise ValueError(msg)
        return cast(dict[str, object], decoded)
    raise RuntimeError(f"control-plane-status endpoint unavailable: {last_error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.control_plane_status",
        description="Fetch runtime control-plane status from Mission Control API.",
    )
    parser.add_argument("--base-url", default="http://localhost:8100")
    parser.add_argument("--token", default="")
    parser.add_argument("--board-id", default=None)
    parser.add_argument("--profile", default="auto")
    parser.add_argument("--timeout-seconds", type=int, default=12)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print single-line JSON output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = fetch_control_plane_status(
            base_url=args.base_url,
            token=args.token,
            board_id=args.board_id,
            profile=args.profile,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - defensive operator output
        print(f"control-plane-status error: {exc}", file=sys.stderr)
        return 1

    if args.compact:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
