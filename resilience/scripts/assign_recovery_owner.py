#!/usr/bin/env python3
"""Deterministic recovery owner election.

Usage:
  python scripts/assign_recovery_owner.py --down-agent FRIDAY --candidates ARSENAL JOCASTA EDITH
"""

from __future__ import annotations

import argparse

PRIORITY = ["FRIDAY", "ARSENAL", "JOCASTA", "EDITH"]


def normalize(name: str) -> str:
    return name.strip().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--down-agent", required=True)
    parser.add_argument("--candidates", nargs="+", required=True)
    args = parser.parse_args()

    down = normalize(args.down_agent)
    candidates = {normalize(c) for c in args.candidates if normalize(c) != down}

    owner = next((a for a in PRIORITY if a in candidates), None)
    if owner is None:
        print("NO_OWNER_AVAILABLE")
        raise SystemExit(2)

    print(owner)


if __name__ == "__main__":
    main()
