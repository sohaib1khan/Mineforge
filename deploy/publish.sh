#!/usr/bin/env bash
# Optional multi-arch publish to GHCR. Not required for local Docker-first use.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-}"
OWNER="${GHCR_OWNER:-${GITHUB_REPOSITORY_OWNER:-}}"
IMAGE_NAME="${GHCR_IMAGE:-mineforge}"

if [[ -z "$VERSION" ]]; then
  echo "usage: $0 <version>   # e.g. 0.9.0" >&2
  exit 1
fi
if [[ -z "$OWNER" ]]; then
  echo "error: set GHCR_OWNER (GitHub user or org)" >&2
  exit 1
fi

TAG="ghcr.io/${OWNER}/${IMAGE_NAME}:${VERSION}"
LATEST="ghcr.io/${OWNER}/${IMAGE_NAME}:latest"

echo "==> Building multi-arch ${TAG}"
docker buildx create --name mineforge-builder --use >/dev/null 2>&1 || docker buildx use mineforge-builder
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f "$ROOT/Dockerfile" \
  --target runtime \
  -t "$TAG" \
  -t "$LATEST" \
  --push \
  "$ROOT"

echo "==> Pushed ${TAG} and ${LATEST}"
