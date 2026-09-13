#!/usr/bin/env bash
# Verify Alembic migrations apply, match the models, and reverse cleanly.
set -euo pipefail

DB="$(mktemp -u).db"
export DATABASE_URL="sqlite:///${DB}"
export SECRET_KEY="verify-secret-key-that-is-long-enough-for-hs256"
export ENV="test"
export AUTH_DEV_MODE="true"

python -m alembic upgrade head
python -m alembic check
python -m alembic downgrade base

echo "Migration checks passed (upgrade, parity, downgrade)."
