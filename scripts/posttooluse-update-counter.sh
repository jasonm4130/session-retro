#!/usr/bin/env bash
# PostToolUse hook: incrementally update score-{session_id}.json with tool counts,
# files touched, and timestamps. Atomic via tmp-then-rename. Silent on success.
set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ -z "$TOOL_NAME" ] && exit 0

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-/tmp/session-retro-data}"
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
mkdir -p "$PLUGIN_DATA"
COUNTER="$PLUGIN_DATA/score-${SESSION_ID}.json"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Load existing or create fresh
if [ -f "$COUNTER" ]; then
    SCORE=$(cat "$COUNTER")
else
    SCORE='{"edits":0,"writes":0,"bash_calls":0,"files_touched":[],"first_tool_ts":null,"last_tool_ts":null,"ran_tests":false,"ran_commit":false}'
fi

# Always update timestamps
SCORE=$(echo "$SCORE" | jq --arg now "$NOW" '
    .last_tool_ts = $now
    | if .first_tool_ts == null then .first_tool_ts = $now else . end
')

case "$TOOL_NAME" in
    Edit)
        FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
        SCORE=$(echo "$SCORE" | jq --arg fp "$FILE_PATH" '
            .edits += 1
            | if ($fp != "" and (.files_touched | index($fp) | not)) then .files_touched += [$fp] else . end
        ')
        ;;
    Write)
        FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
        SCORE=$(echo "$SCORE" | jq --arg fp "$FILE_PATH" '
            .writes += 1
            | if ($fp != "" and (.files_touched | index($fp) | not)) then .files_touched += [$fp] else . end
        ')
        ;;
    Bash)
        CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
        SCORE=$(echo "$SCORE" | jq '.bash_calls += 1')
        case "$CMD" in
            *pytest*|*"jest "*|*"go test"*|*"cargo test"*|*"npm test"*|*"npm run test"*|*"bun test"*|*"yarn test"*)
                SCORE=$(echo "$SCORE" | jq '.ran_tests = true')
                ;;
        esac
        case "$CMD" in
            *"git commit"*)
                SCORE=$(echo "$SCORE" | jq '.ran_commit = true')
                ;;
        esac
        ;;
esac

# Atomic write
TMP=$(mktemp "${COUNTER}.XXXXXX")
echo "$SCORE" > "$TMP"
mv "$TMP" "$COUNTER"
exit 0
