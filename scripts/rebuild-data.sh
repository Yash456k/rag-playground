#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

skip_frontend=false
if [[ "${1:-}" == "--skip-frontend" ]]; then
  skip_frontend=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--skip-frontend]" >&2
  exit 2
fi

docker_cmd=(docker)
if ! docker info >/dev/null 2>&1; then
  if sudo -n docker info >/dev/null 2>&1; then
    docker_cmd=(sudo -n docker)
  else
    echo "Docker is unavailable. Run this as a user with Docker access." >&2
    exit 1
  fi
fi

compose=("${docker_cmd[@]}" compose)
api_was_stopped=false

restore_api() {
  if [[ "$api_was_stopped" == true ]]; then
    echo "Rebuild failed; bringing the API back up with the available image." >&2
    "${compose[@]}" up -d api proxy || true
  fi
}
trap restore_api ERR

echo "[1/6] Validating repository configuration"
"${compose[@]}" --env-file .env config --quiet

echo "[2/6] Running frontend checks and production build"
if [[ "$skip_frontend" == true ]]; then
  echo "Skipping frontend checks by request."
elif command -v npm >/dev/null 2>&1; then
  npm --prefix frontend ci
  npm --prefix frontend run check
  npm --prefix frontend run build
else
  echo "npm is not installed here; frontend build is handled by Vercel." >&2
fi

echo "[3/6] Building the current API image"
"${compose[@]}" build api

echo "[4/6] Starting PostgreSQL and stopping the resident model process"
"${compose[@]}" up -d --wait --wait-timeout 120 db
"${compose[@]}" stop api
api_was_stopped=true

echo "[5/6] Re-reading corpus data and regenerating every embedding column"
"${compose[@]}" run --rm --no-deps api python -m app.ingest --corpus /app/corpus

echo "[6/6] Starting the API and proxy, then checking health"
"${compose[@]}" up -d --wait --wait-timeout 240 api proxy
api_was_stopped=false
trap - ERR

health_url="${PUBLIC_API_URL:-}"
if [[ -z "$health_url" && -f .env ]]; then
  health_url="$(grep -E '^PUBLIC_API_URL=' .env | tail -n 1 | cut -d= -f2-)"
fi
if [[ -n "$health_url" ]]; then
  curl --fail --silent --show-error "${health_url%/}/v1/health" >/dev/null
  echo "Healthy: ${health_url%/}/v1/health"
else
  echo "Stack is healthy according to Docker; PUBLIC_API_URL was not set for the HTTP check."
fi

echo "Data rebuild complete. Commit corpus changes so Vercel can rebuild the frontend if needed."
