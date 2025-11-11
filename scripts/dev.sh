#!/usr/bin/env bash
set -euo pipefail

# Run backend and frontend from local source via Docker Compose (builds images)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/data"
mkdir -p "$ROOT_DIR/stockfish"

echo "Starting Local Chess Analyzer (from source)..."
echo "- Backend: http://localhost:42069 (docs at /docs)"
echo "- Frontend: http://localhost:6969"
echo

cleanup() {
  echo
  echo "Stopping containers..."
  docker compose -f docker-compose.yml down
}
trap cleanup INT TERM

docker compose -f docker-compose.yml up --build


