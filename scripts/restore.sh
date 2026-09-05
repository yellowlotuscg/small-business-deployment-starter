#!/usr/bin/env bash
# Restore a backup into the local data dir. Refuses to overwrite without --force.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ $# -lt 1 ]; then
  echo "usage: restore.sh <backup.db> [--force]" >&2
  echo "  --force replaces an existing database at DATA_DIR/app.db" >&2
  exit 2
fi

BACKUP="$1"
FORCE="${2:-}"
DATA_DIR="${DATA_DIR:-./data}"

if [ ! -f "$BACKUP" ]; then
  echo "restore.sh: backup file not found: $BACKUP" >&2
  exit 1
fi

if [ -n "$FORCE" ] && [ "$FORCE" != "--force" ]; then
  echo "restore.sh: unknown flag: $FORCE" >&2
  exit 2
fi

if [ "$FORCE" = "--force" ]; then
  python3 -m app.maintenance restore --backup "$BACKUP" --data-dir "$DATA_DIR" --force
else
  python3 -m app.maintenance restore --backup "$BACKUP" --data-dir "$DATA_DIR"
fi
