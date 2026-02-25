#!/usr/bin/env bash
set -euo pipefail

# Build and publish immutable backend/frontend images to GHCR.
# Usage:
#   GHCR_USERNAME=Matt-Aurora-Ventures GHCR_TOKEN=*** ./scripts/release_images.sh
#
# Optional:
#   REGISTRY_IMAGE=ghcr.io/matt-aurora-ventures/jarvis
#   API_URL=http://76.13.106.100:8100
#   AUTH_MODE=local

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REGISTRY_IMAGE="${REGISTRY_IMAGE:-ghcr.io/matt-aurora-ventures/jarvis}"
API_URL="${API_URL:-http://76.13.106.100:8100}"
AUTH_MODE="${AUTH_MODE:-local}"
SHA="$(git rev-parse --short=12 HEAD)"
UTC_TAG="$(date -u +%Y%m%dt%H%M%sz | tr '[:upper:]' '[:lower:]')"

BACKEND_TAG="kr8tiv-mc-backend-${SHA}-${UTC_TAG}"
FRONTEND_TAG="kr8tiv-mc-frontend-${SHA}-${UTC_TAG}"
BACKEND_IMAGE="${REGISTRY_IMAGE}:${BACKEND_TAG}"
FRONTEND_IMAGE="${REGISTRY_IMAGE}:${FRONTEND_TAG}"

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  : "${GHCR_USERNAME:?GHCR_USERNAME is required when GHCR_TOKEN is set}"
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
fi

docker build -f backend/Dockerfile -t "$BACKEND_IMAGE" .
docker build -f frontend/Dockerfile -t "$FRONTEND_IMAGE" \
  --build-arg "NEXT_PUBLIC_API_URL=${API_URL}" \
  --build-arg "NEXT_PUBLIC_AUTH_MODE=${AUTH_MODE}" \
  frontend

docker push "$BACKEND_IMAGE"
docker push "$FRONTEND_IMAGE"

cat <<EOF
Published images:
  BACKEND_IMAGE=${BACKEND_IMAGE}
  FRONTEND_IMAGE=${FRONTEND_IMAGE}

Suggested compose pins:
  backend.image=${BACKEND_IMAGE}
  webhook-worker.image=${BACKEND_IMAGE}
  frontend.image=${FRONTEND_IMAGE}
EOF

