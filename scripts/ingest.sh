#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if docker compose ps --status running api | grep -q rag-playground-api; then
  echo "Refusing to start a second model process while the API is running." >&2
  echo "Run: docker compose stop api && ./scripts/ingest.sh && docker compose start api" >&2
  exit 1
fi

docker compose up -d --wait --wait-timeout 120 db
docker compose run --rm --no-deps api python -m app.ingest --corpus /app/corpus
