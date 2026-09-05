#!/usr/bin/env bash
# Roll back releases/current to the previously released version by swapping
# the state file pointers. Snapshots are never deleted. No-op when there is
# no previous release.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RELEASES_DIR="$ROOT/releases"
STATE_FILE="$RELEASES_DIR/state"

if [ ! -f "$STATE_FILE" ]; then
  echo "rollback.sh: no releases recorded yet (run release.sh first)" >&2
  exit 3
fi

CURRENT="$(sed -n 's/^current=//p' "$STATE_FILE")"
PREVIOUS="$(sed -n 's/^previous=//p' "$STATE_FILE")"

if [ -z "$PREVIOUS" ]; then
  echo "rollback.sh: no previous release to roll back to (current is $CURRENT)" >&2
  exit 3
fi

if [ ! -d "$RELEASES_DIR/$PREVIOUS" ]; then
  echo "rollback.sh: previous snapshot missing at $RELEASES_DIR/$PREVIOUS" >&2
  exit 3
fi

printf 'previous=%s\ncurrent=%s\n' "$CURRENT" "$PREVIOUS" > "$STATE_FILE"
ln -sfn "$PREVIOUS" "$RELEASES_DIR/current"
printf '%s rollback %s -> %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$CURRENT" "$PREVIOUS" >> "$RELEASES_DIR/history.log"

echo "rollback.sh: releases/current now points to $PREVIOUS (was $CURRENT)"
