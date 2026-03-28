#!/usr/bin/env python3
"""Detect secret-like patterns in a directory or zip file.

Fails with non-zero exit when suspicious tokens are found.
"""

from __future__ import annotations

import argparse
import re
import tempfile
import zipfile
from pathlib import Path

PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_-]{20,}\b"),
]

ALLOW = {"__INJECT_AT_RUNTIME__"}


def scan_text(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    if any(allow in text for allow in ALLOW):
        text = text.replace("__INJECT_AT_RUNTIME__", "")
    for pattern in PATTERNS:
        for m in pattern.findall(text):
            findings.append(f"{path}: {m[:12]}...")
    return findings


def scan_path(root: Path) -> list[str]:
    findings: list[str] = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".tgz", ".mp4"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        findings.extend(scan_text(f, text))
    return findings


def extract_zip_safely(zip_path: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for entry in zf.infolist():
            if "\x00" in entry.filename:
                raise ValueError(f"Unsafe ZIP entry: {entry.filename!r}")
            candidate = (root / entry.filename).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Unsafe ZIP entry: {entry.filename!r}") from exc
        zf.extractall(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, type=Path)
    args = parser.parse_args()

    target = args.path
    if not target.exists():
        raise SystemExit(f"Path not found: {target}")

    if target.is_file() and target.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory() as td:
            extract_zip_safely(target, Path(td))
            findings = scan_path(Path(td))
    else:
        findings = scan_path(target)

    if findings:
        print("SECRET_PATTERNS_DETECTED")
        for line in findings:
            print(line)
        raise SystemExit(3)

    print("OK_NO_SECRET_PATTERNS")


if __name__ == "__main__":
    main()
