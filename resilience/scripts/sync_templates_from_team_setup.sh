#!/usr/bin/env bash
set -euo pipefail

MANIFEST_PATH="${1:-config/template-manifest.yaml}"
if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "Missing manifest: $MANIFEST_PATH" >&2
  exit 1
fi

mapfile -t ENTRIES < <(
  MANIFEST_PATH="$MANIFEST_PATH" python - <<'PY'
from pathlib import Path
import os
import yaml

manifest = yaml.safe_load(Path(os.environ["MANIFEST_PATH"]).read_text(encoding="utf-8"))
for item in manifest.get("templates", []):
    print(f"{item['source']}\t{item['target']}")
PY
)

for entry in "${ENTRIES[@]}"; do
  src="${entry%%$'\t'*}"
  dst="${entry#*$'\t'}"
  if [[ ! -f "$src" ]]; then
    echo "Missing source template: $src" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  checksum="$(sha256sum "$dst" | awk '{print $1}')"
  echo "synced $src -> $dst ($checksum)"
done
