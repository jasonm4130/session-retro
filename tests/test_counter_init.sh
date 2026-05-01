#!/usr/bin/env bash
# First PostToolUse call creates the counter file with edits=1, the file_path tracked.
set -euo pipefail
WORKDIR=$(mktemp -d)
trap "rm -rf $WORKDIR" EXIT
export CLAUDE_PLUGIN_DATA="$WORKDIR"
export CLAUDE_SESSION_ID="test-counter-init"

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/scripts/posttooluse-update-counter.sh"

# Simulate a PostToolUse hook payload for an Edit
echo '{"tool_name":"Edit","tool_input":{"file_path":"/repo/src/foo.ts"}}' | bash "$SCRIPT"

COUNTER="$WORKDIR/score-test-counter-init.json"
[ -f "$COUNTER" ] || { echo "FAIL: counter file $COUNTER not created"; exit 1; }

EDITS=$(jq '.edits' < "$COUNTER")
[ "$EDITS" = "1" ] || { echo "FAIL: edits should be 1, got $EDITS"; exit 1; }

FILES=$(jq -r '.files_touched | length' < "$COUNTER")
[ "$FILES" = "1" ] || { echo "FAIL: files_touched len should be 1, got $FILES"; exit 1; }

FIRST=$(jq -r '.files_touched[0]' < "$COUNTER")
[ "$FIRST" = "/repo/src/foo.ts" ] || { echo "FAIL: file should be /repo/src/foo.ts, got $FIRST"; exit 1; }

echo "PASS"
