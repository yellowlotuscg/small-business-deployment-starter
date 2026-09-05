#!/usr/bin/env bash
# Local release snapshot. Runs the full test suite first, then records the
# release under releases/<version>/ and points releases/current at it.
# Everything stays inside the repo. No network, no registry, no deletion.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "release.sh: version must look like 1.2.3 (got '${VERSION}')" >&2
  exit 2
fi

if [ ! -f "app/__init__.py" ] || [ ! -d "tests" ]; then
  echo "release.sh: expected app/ and tests/ under the repo root" >&2
  exit 2
fi

RELEASES_DIR="$ROOT/releases"
STATE_FILE="$RELEASES_DIR/state"
TARGET="$RELEASES_DIR/$VERSION"

if [ -d "$TARGET" ]; then
  echo "release.sh: $VERSION already released at $TARGET" >&2
  exit 2
fi

echo "release.sh: running test suite before release $VERSION"
python3 -m unittest discover -s tests -q

mkdir -p "$TARGET"
cp -R app "$TARGET/app"
cp VERSION "$TARGET/VERSION"

OLD_CURRENT=""
if [ -f "$STATE_FILE" ]; then
  OLD_CURRENT="$(sed -n 's/^current=//p' "$STATE_FILE")"
fi

printf 'previous=%s\ncurrent=%s\n' "$OLD_CURRENT" "$VERSION" > "$STATE_FILE"
ln -sfn "$VERSION" "$RELEASES_DIR/current"
printf '%s release %s (previous %s)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$VERSION" "${OLD_CURRENT:-none}" >> "$RELEASES_DIR/history.log"

echo "release.sh: tests passed, release $VERSION ready at $TARGET"
echo "release.sh: releases/current now points to $VERSION"
