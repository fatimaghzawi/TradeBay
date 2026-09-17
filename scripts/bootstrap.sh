#!/usr/bin/env bash
# Bootstrap local development (copy env, hint next steps)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example — fill in secrets before production use."
else
  echo ".env already exists"
fi
echo "Next: docker compose up mongodb -d && make install && make backend"
