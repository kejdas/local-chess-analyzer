#!/usr/bin/env bash
set -euo pipefail

# Run published Docker images (no local build required).
# You can override via env vars, e.g.:
#   IMAGE_OWNER=tarekchaalan TAG=latest BACKEND_HOST_PORT=42069 FRONTEND_HOST_PORT=6969 bash scripts/run-images.sh

IMAGE_OWNER="${IMAGE_OWNER:-tarekchaalan}"
TAG="${TAG:-latest}"

BACKEND_IMAGE="ghcr.io/${IMAGE_OWNER}/local-chess-analyzer-backend:${TAG}"
FRONTEND_IMAGE="ghcr.io/${IMAGE_OWNER}/local-chess-analyzer-frontend:${TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p "${ROOT_DIR}/data"

# Host ports (override as env if needed)
BACKEND_HOST_PORT="${BACKEND_HOST_PORT:-42069}"
FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT:-6969}"

# Only mount stockfish if a binary exists locally; otherwise don't mask the image content.
STOCKFISH_BIN="${ROOT_DIR}/stockfish/stockfish_binary"
if [[ -f "${STOCKFISH_BIN}" && -x "${STOCKFISH_BIN}" ]]; then
  STOCKFISH_VOLUME="      - \"${ROOT_DIR}/stockfish:/app/stockfish:ro\""
else
  STOCKFISH_VOLUME=""
fi

# If your backend supports CORS toggles, wire them here (adjust var name to your app).
# Example:
# BACKEND_ENV_YAML=$'    environment:\n      - CORS_ORIGIN=http://localhost:'"$FRONTEND_HOST_PORT"
BACKEND_ENV_YAML=""

COMPOSE_FILE="$(mktemp -t lca-compose.XXXXXX.yml)"
cat > "${COMPOSE_FILE}" <<YAML
version: '3.8'

services:
  backend:
    image: ${BACKEND_IMAGE}
    container_name: lca-backend
    hostname: backend
$( [[ -n "${BACKEND_ENV_YAML}" ]] && echo "${BACKEND_ENV_YAML}" )
    volumes:
      - "${ROOT_DIR}/data:/app/data"
$( [[ -n "${STOCKFISH_VOLUME}" ]] && echo "${STOCKFISH_VOLUME}" )
    ports:
      - "${BACKEND_HOST_PORT}:42069"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:42069/')"]
      interval: 10s
      timeout: 3s
      retries: 10

  frontend:
    image: ${FRONTEND_IMAGE}
    container_name: lca-frontend
    depends_on:
      backend:
        condition: service_healthy
    # If your frontend's Nginx template uses envsubst, pass the upstream here.
    # It must reference \$API_UPSTREAM in its default.conf template.
    environment:
      - API_UPSTREAM=backend:42069
      - API_ORIGIN=http://localhost:${FRONTEND_HOST_PORT}
    ports:
      - "${FRONTEND_HOST_PORT}:80"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/ || exit 1"]
      interval: 10s
      timeout: 3s
      retries: 10
YAML

echo "Using images:"
echo "  Backend : ${BACKEND_IMAGE}"
echo "  Frontend: ${FRONTEND_IMAGE}"
echo
echo "Backend  -> http://localhost:${BACKEND_HOST_PORT} (docs at /docs)"
echo "Frontend -> http://localhost:${FRONTEND_HOST_PORT}"
echo

# Clean up compose file on normal exit; stop containers on signals.
cleanup_down() {
  echo
  echo "Stopping containers..."
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans || true
  rm -f "${COMPOSE_FILE}"
}
cleanup_file() {
  rm -f "${COMPOSE_FILE}"
}
trap cleanup_down INT TERM
trap cleanup_file EXIT

# Run detached so the app survives terminal closure; logs are still viewable.
docker compose -f "${COMPOSE_FILE}" up -d

echo "Waiting for healthchecks..."
# Wait for frontend to become healthy (up to ~30s)
for _ in {1..30}; do
  if docker inspect -f '{{.State.Health.Status}}' lca-frontend 2>/dev/null | grep -q healthy; then
    echo "Ready."
    echo "Open http://localhost:${FRONTEND_HOST_PORT}"
    exit 0
  fi
  sleep 1
done

echo "Services did not become healthy in time. Check logs:"
echo "  docker logs lca-backend"
echo "  docker logs lca-frontend"
exit 1