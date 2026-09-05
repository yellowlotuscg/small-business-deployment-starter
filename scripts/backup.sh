#!/usr/bin/env bash
# WAL-safe backup of the local demo database. Path-scoped, additive only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATA_DIR="${DATA_DIR:-./data}"
OUT="${1:-}"

if [ ! -f "$DATA_DIR/app.db" ]; then
  echo "backup.sh: no database at $DATA_DIR/app.db (seed first: python3 -m app.seed)" >&2
  exit 1
fi

if [ -n "$OUT" ]; then
  python3 -m app.maintenance backup --data-dir "$DATA_DIR" --out "$OUT"
else
  python3 -m app.maintenance backup --data-dir "$DATA_DIR"
fi
