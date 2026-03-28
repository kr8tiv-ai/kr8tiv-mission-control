#!/usr/bin/env python3
"""Sanitize OpenClaw config exports for public publication.

Removes known secret-bearing keys recursively and replaces sensitive values with
"__INJECT_AT_RUNTIME__".
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SENSITIVE_KEY_PARTS = {
    "token",
    "apikey",
    "api_key",
    "secret",
    "password",
    "oauth",
    "auth",
    "privatekey",
    "private_key",
    "bearer",
    "cookie",
}

REDACT_VALUE = "__INJECT_AT_RUNTIME__"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _sanitize(node: Any) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            if _is_sensitive_key(k):
                out[k] = REDACT_VALUE
            else:
                out[k] = _sanitize(v)
        return out
    if isinstance(node, list):
        return [_sanitize(item) for item in node]
    return node


def sanitize_file(src: Path, dst: Path) -> None:
    # Accept UTF-8 with or without BOM from ad-hoc exports.
    data = json.loads(src.read_text(encoding="utf-8-sig"))
    sanitized = _sanitize(data)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(sanitized, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    files = sorted(args.input_dir.rglob("*.json"))
    if not files:
        raise SystemExit("No JSON files found to sanitize")

    for src in files:
        rel = src.relative_to(args.input_dir)
        dst = args.output_dir / rel
        sanitize_file(src, dst)
        print(f"sanitized: {rel}")


if __name__ == "__main__":
    main()
