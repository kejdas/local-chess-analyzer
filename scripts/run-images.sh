#!/usr/bin/env bash
set -euo pipefail

# Run published Docker images with robust checks and clear errors.

#######################################
# Config (override via env)
#######################################
IMAGE_OWNER="${IMAGE_OWNER:-tarekchaalan}"
TAG="${TAG:-latest}"
BACKEND_HOST_PORT="${BACKEND_HOST_PORT:-42069}"
FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT:-6969}"
# When set to 1, automatically bump to the next free port if a port is busy.
AUTO_PORT="${AUTO_PORT:-0}"
# Max seconds to wait for health before failing
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-45}"

BACKEND_IMAGE="ghcr.io/${IMAGE_OWNER}/local-chess-analyzer-backend:${TAG}"
FRONTEND_IMAGE="ghcr.io/${IMAGE_OWNER}/local-chess-analyzer-frontend:${TAG}"

#######################################
# Utility
#######################################
err() { printf "ERROR: %s\n" "$*" >&2; }
info() { printf "%s\n" "$*"; }
die() { err "$*"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command '$1' not found. Install it and retry."
}

detect_os() {
  case "$(uname -s || true)" in
    Darwin) echo "macOS" ;;
    Linux) echo "Linux" ;;
    MINGW*|MSYS*|CYGWIN*) echo "Windows" ;;
    *) echo "Unknown" ;;
  esac
}

compose_bin() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    die "Neither 'docker compose' nor 'docker-compose' is available. Update Docker Desktop or install docker-compose."
  fi
}

is_wsl() {
  # Detect WSL by /proc/version
  if [ -f /proc/version ] && grep -qi "microsoft" /proc/version 2>/dev/null; then
    return 0
  fi
  return 1
}

open_default_browser() {
  local url="$1"
  case "$OS" in
    macOS)
      if command -v open >/dev/null 2>&1; then
        open "$url" >/dev/null 2>&1 || true
      fi
      ;;
    Windows)
      # Use PowerShell from Git Bash to open default browser
      if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '$url'" >/dev/null 2>&1 || true
      elif command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start "" "$url" >/dev/null 2>&1 || true
      fi
      ;;
    Linux)
      if is_wsl && command -v powershell.exe >/dev/null 2>&1; then
        # On WSL, prefer opening Windows default browser
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '$url'" >/dev/null 2>&1 || true
      elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 || true
      fi
      ;;
    *)
      ;;
  esac
}

port_in_use() {
  # Returns 0 if port is in use, 1 if free.
  local port="$1"
  # Prefer lsof, then nc, then netstat, then /dev/tcp
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1 && return 0 || return 1
  elif command -v nc >/dev/null 2>&1; then
    nc -z localhost "$port" >/dev/null 2>&1 && return 0 || return 1
  elif command -v netstat >/dev/null 2>&1; then
    netstat -an | grep -qE "LISTEN[^0-9]*.*[:\.]$port[[:space:]]" && return 0 || return 1
  else
    # bash /dev/tcp: if connect succeeds, it's in use
    (echo >"/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1 && return 0 || return 1
  fi
}

next_free_port() {
  local start="$1"
  local p="$start"
  for _ in {1..50}; do
    if ! port_in_use "$p"; then
      echo "$p"
      return 0
    fi
    p=$((p+1))
  done
  echo "" # none found
  return 1
}

#######################################
# Preflight checks
#######################################
OS="$(detect_os)"

require_cmd docker

# Try to ensure Docker daemon is running (best-effort per OS)
ensure_docker_running() {
  local timeout="${1:-120}" # seconds
  local start_ts end_ts
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  case "$OS" in
    macOS)
      # Try to launch Docker.app if present
      if [ -d "/Applications/Docker.app" ] || [ -d "$HOME/Applications/Docker.app" ]; then
        info "Starting Docker Desktop..."
        open -a Docker || true
      fi
      ;;
    Windows)
      # If running under Git Bash/MinGW, attempt PowerShell launch
      if command -v powershell.exe >/dev/null 2>&1; then
        info "Attempting to start Docker Desktop via PowerShell..."
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath \"$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe\"" >/dev/null 2>&1 || true
      fi
      ;;
    Linux)
      # Try user-level systemd first, then system service (no sudo prompts)
      if command -v systemctl >/dev/null 2>&1; then
        systemctl --user start docker >/dev/null 2>&1 || systemctl start docker >/dev/null 2>&1 || true
      fi
      ;;
    *)
      ;;
  esac
  # Wait loop
  start_ts=$(date +%s)
  end_ts=$((start_ts + timeout))
  info "Waiting for Docker daemon to become ready (up to ${timeout}s)..."
  while [ "$(date +%s)" -lt "$end_ts" ]; do
    if docker info >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

if ! ensure_docker_running 120; then
  case "$OS" in
    macOS)
      die "Docker daemon not running. Open Docker Desktop and wait until it says 'Engine running', then retry."
      ;;
    Windows)
      die "Docker daemon not running. Start Docker Desktop and ensure the Linux engine is running, then retry."
      ;;
    Linux)
      die "Docker daemon not reachable. Start it with 'sudo systemctl start docker' or ensure your user is in the 'docker' group."
      ;;
    *)
      die "Docker daemon not reachable. Start Docker and retry."
      ;;
  esac
fi

COMPOSE="$(compose_bin)"

# ---------------------------
# Optional: fetch Stockfish
# ---------------------------
download_stockfish_linux() {
  info "Downloading Stockfish (Linux) into ./stockfish via temporary Ubuntu container..."
  mkdir -p "${ROOT_DIR}/stockfish"
  # Use an Ubuntu container to install stockfish and copy the binary to host
  if ! docker run --rm -v "${ROOT_DIR}/stockfish:/out" ubuntu:22.04 bash -lc "set -euo pipefail; apt-get update >/dev/null; DEBIAN_FRONTEND=noninteractive apt-get install -y stockfish >/dev/null; cp /usr/games/stockfish /out/stockfish_binary; chmod +x /out/stockfish_binary"; then
    err "Failed to obtain Stockfish via Ubuntu container."
    err "You can try manually placing a Linux stockfish binary at: ${ROOT_DIR}/stockfish/stockfish_binary"
    return 1
  fi
  info "Stockfish saved to ${ROOT_DIR}/stockfish/stockfish_binary"
}

# Ports
orig_backend_port="$BACKEND_HOST_PORT"
orig_frontend_port="$FRONTEND_HOST_PORT"

if port_in_use "$BACKEND_HOST_PORT"; then
  if [ "$AUTO_PORT" = "1" ]; then
    newp="$(next_free_port "$BACKEND_HOST_PORT")" || die "All candidate backend ports near $BACKEND_HOST_PORT are busy."
    info "Backend port $BACKEND_HOST_PORT busy. Using $newp."
    BACKEND_HOST_PORT="$newp"
  else
    die "Backend port $BACKEND_HOST_PORT is already in use. Set BACKEND_HOST_PORT to a free port or export AUTO_PORT=1."
  fi
fi

if port_in_use "$FRONTEND_HOST_PORT"; then
  if [ "$AUTO_PORT" = "1" ]; then
    newp="$(next_free_port "$FRONTEND_HOST_PORT")" || die "All candidate frontend ports near $FRONTEND_HOST_PORT are busy."
    info "Frontend port $FRONTEND_HOST_PORT busy. Using $newp."
    FRONTEND_HOST_PORT="$newp"
  else
    die "Frontend port $FRONTEND_HOST_PORT is already in use. Set FRONTEND_HOST_PORT to a free port or export AUTO_PORT=1."
  fi
fi

#######################################
# Paths and optional mounts
#######################################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p "${ROOT_DIR}/data"

STOCKFISH_BIN="${ROOT_DIR}/stockfish/stockfish_binary"
# Prompt to download Stockfish if missing
if [[ ! -f "${STOCKFISH_BIN}" ]]; then
  if [[ -t 0 ]]; then
    echo
    read -r -p "Stockfish engine not found locally. Download Linux Stockfish now to \"${STOCKFISH_BIN}\"? [y/N] " _ans
    if [[ "${_ans}" == "y" || "${_ans}" == "Y" ]]; then
      download_stockfish_linux || true
    else
      info "Skipping Stockfish download. Analysis features may be limited unless the backend image bundles it."
    fi
  else
    info "Stockfish not found and no TTY for prompt; skipping automatic download."
  fi
fi

if [[ -f "${STOCKFISH_BIN}" && -x "${STOCKFISH_BIN}" ]]; then
  STOCKFISH_VOLUME="      - \"${ROOT_DIR}/stockfish:/app/stockfish:ro\""
else
  STOCKFISH_VOLUME=""
fi

BACKEND_ENV_YAML=""

#######################################
# Pull images first with explicit errors
#######################################
info "Pulling images..."
if ! docker pull "$BACKEND_IMAGE" >/dev/null 2>&1; then
  err "Failed to pull backend image: $BACKEND_IMAGE"
  err "Possible causes: image tag '$TAG' does not exist, network issues, or GHCR auth required."
  err "Try: docker login ghcr.io   or verify the image name/tag."
  exit 1
fi
if ! docker pull "$FRONTEND_IMAGE" >/dev/null 2>&1; then
  err "Failed to pull frontend image: $FRONTEND_IMAGE"
  err "Possible causes: image tag '$TAG' does not exist, network issues, or GHCR auth required."
  exit 1
fi

#######################################
# Compose file
#######################################
COMPOSE_FILE="$(mktemp -t lca-compose.XXXXXX.yml)"
cat > "${COMPOSE_FILE}" <<YAML
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

#######################################
# Cleanup on exit
#######################################
cleanup_down() {
  echo
  info "Stopping containers..."
  ${COMPOSE} -f "${COMPOSE_FILE}" down --remove-orphans >/dev/null 2>&1 || true
  rm -f "${COMPOSE_FILE}"
}
cleanup_file() { rm -f "${COMPOSE_FILE}"; }
trap cleanup_down INT TERM
trap cleanup_file EXIT

#######################################
# Run
#######################################
info "Using images:"
info "  Backend : ${BACKEND_IMAGE}"
info "  Frontend: ${FRONTEND_IMAGE}"
echo
info "Backend  -> http://localhost:${BACKEND_HOST_PORT} (docs at /docs)"
info "Frontend -> http://localhost:${FRONTEND_HOST_PORT}"
echo

# Bring up
if ! ${COMPOSE} -f "${COMPOSE_FILE}" up -d; then
  err "Compose failed to start services."
  err "Check for port conflicts, missing privileges, or incompatible Docker versions."
  exit 1
fi

#######################################
# Health + Reachability checks
#######################################
info "Waiting for health checks (up to ${HEALTH_TIMEOUT}s)..."
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
backend_ok=0
frontend_ok=0

# Wait backend healthy
while [ "$(date +%s)" -lt "$deadline" ]; do
  status="$(docker inspect -f '{{.State.Health.Status}}' lca-backend 2>/dev/null || echo "unknown")"
  if [ "$status" = "healthy" ]; then backend_ok=1; break; fi
  sleep 1
done

if [ "$backend_ok" -ne 1 ]; then
  err "Backend did not become healthy."
  err "Logs: docker logs lca-backend"
  err "If the port ${BACKEND_HOST_PORT} was blocked by a firewall, open it locally."
  exit 1
fi

# Wait frontend healthy
while [ "$(date +%s)" -lt "$deadline" ]; do
  status="$(docker inspect -f '{{.State.Health.Status}}' lca-frontend 2>/dev/null || echo "unknown")"
  if [ "$status" = "healthy" ]; then frontend_ok=1; break; fi
  sleep 1
done

if [ "$frontend_ok" -ne 1 ]; then
  err "Frontend did not become healthy."
  err "Logs: docker logs lca-frontend"
  err "If Nginx cannot reach backend, ensure containers share the default network and API_UPSTREAM=backend:42069."
  exit 1
fi

# Verify local port reachability
if ! curl -fsS "http://localhost:${FRONTEND_HOST_PORT}/" >/dev/null 2>&1; then
  err "Frontend is healthy in container but not reachable on localhost:${FRONTEND_HOST_PORT}."
  err "Possible causes: local firewall, VPN, or security software blocking inbound connections."
  err "Try a different port via FRONTEND_HOST_PORT or disable the blocker."
  exit 1
fi

info "Ready."
info "Open http://localhost:${FRONTEND_HOST_PORT}"

# Best-effort: open default browser
open_default_browser "http://localhost:${FRONTEND_HOST_PORT}"

# Summary of common failures and remedies
cat <<'EOF'

If something fails:
- "docker: command not found": Install Docker Desktop (macOS/Windows) or Docker Engine (Linux).
- "Cannot connect to the Docker daemon": Start Docker Desktop or run "sudo systemctl start docker" on Linux.
- Port already in use: set BACKEND_HOST_PORT/FRONTEND_HOST_PORT to free ports, or export AUTO_PORT=1.
- GHCR pull errors: run "docker login ghcr.io" or verify IMAGE_OWNER/TAG.
- Healthcheck never healthy: "docker logs lca-backend" / "docker logs lca-frontend" for stack traces.
- Local firewall/VPN blocks: open the chosen ports or temporarily disable blockers.

EOF

exit 0