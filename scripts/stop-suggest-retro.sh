#!/usr/bin/env bash
# Stop hook: aggregate events-{session_id}.jsonl, evaluate thresholds, emit
# additionalContext suggestion if retro-worthy AND no retro fired this session.
# Silent otherwise. Cost target <50ms per invocation.
set -euo pipefail

# Drain hook stdin (we don't need it — all signal comes from the event log)
cat >/dev/null

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-/tmp/session-retro-data}"
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
EVENTS="$PLUGIN_DATA/events-${SESSION_ID}.jsonl"
FIRED_FLAG="$PLUGIN_DATA/retro-fired-${SESSION_ID}.flag"

# No events recorded yet → no work to suggest a retro on
[ -f "$EVENTS" ] || exit 0
# Already retro'd this session → suppress
[ -f "$FIRED_FLAG" ] && exit 0

# Single-pass aggregation via jq -s (slurp all JSONL lines into one array)
AGG=$(jq -s '
    {
        edits: ([.[] | select(.tool == "Edit")] | length),
        writes: ([.[] | select(.tool == "Write")] | length),
        bash_calls: ([.[] | select(.tool == "Bash")] | length),
        files_touched: ([.[] | select(.tool == "Edit" or .tool == "Write") | .input.file_path // empty] | map(select(. != "")) | unique | length),
        first_ts: ([.[].ts] | min),
        last_ts: ([.[].ts] | max),
        ran_tests: ([.[] | select(.tool == "Bash") | .input.command // ""] | any(test("pytest|jest |go test|cargo test|npm test|npm run test|bun test|yarn test"))),
        ran_commit: ([.[] | select(.tool == "Bash") | .input.command // ""] | any(test("git commit")))
    }
' < "$EVENTS")

EDITS=$(echo "$AGG" | jq -r '.edits')
WRITES=$(echo "$AGG" | jq -r '.writes')
BASH_CALLS=$(echo "$AGG" | jq -r '.bash_calls')
FILES_COUNT=$(echo "$AGG" | jq -r '.files_touched')
RAN_TESTS=$(echo "$AGG" | jq -r '.ran_tests')
RAN_COMMIT=$(echo "$AGG" | jq -r '.ran_commit')
FIRST_TS=$(echo "$AGG" | jq -r '.first_ts // empty')
LAST_TS=$(echo "$AGG" | jq -r '.last_ts // empty')

# Compute duration in seconds — handle BSD (macOS) and GNU date
DURATION_SEC=0
if [ -n "$FIRST_TS" ] && [ -n "$LAST_TS" ]; then
    if date -u -d "$LAST_TS" +%s >/dev/null 2>&1; then
        FIRST_S=$(date -u -d "$FIRST_TS" +%s)
        LAST_S=$(date -u -d "$LAST_TS" +%s)
    else
        FIRST_S=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$FIRST_TS" +%s 2>/dev/null || echo 0)
        LAST_S=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$LAST_TS" +%s 2>/dev/null || echo 0)
    fi
    DURATION_SEC=$((LAST_S - FIRST_S))
fi
DURATION_MIN=$((DURATION_SEC / 60))
TOTAL_TOOLS=$((EDITS + WRITES + BASH_CALLS))
EDIT_WRITE=$((EDITS + WRITES))

# Threshold evaluation — any one triggers
TRIGGER=false
TRIGGER_REASON=""
if [ "$EDIT_WRITE" -ge 3 ] && [ "$FILES_COUNT" -ge 2 ]; then
    TRIGGER=true; TRIGGER_REASON="${EDIT_WRITE} edits across ${FILES_COUNT} files"
elif [ "$DURATION_SEC" -ge 1200 ]; then
    TRIGGER=true; TRIGGER_REASON="${DURATION_MIN} minutes of work"
elif [ "$RAN_COMMIT" = "true" ]; then
    TRIGGER=true; TRIGGER_REASON="committed during session"
elif [ "$RAN_TESTS" = "true" ] && [ "$EDIT_WRITE" -ge 2 ]; then
    TRIGGER=true; TRIGGER_REASON="ran tests + ${EDIT_WRITE} edits"
elif [ "$TOTAL_TOOLS" -ge 30 ]; then
    TRIGGER=true; TRIGGER_REASON="${TOTAL_TOOLS} tool calls"
fi

[ "$TRIGGER" = "false" ] && exit 0

MSG="[session-retro] This session: ${TRIGGER_REASON}. Suggest running /retro to capture decisions/learnings before /clear."
jq -n --arg msg "$MSG" '{
    hookSpecificOutput: {
        hookEventName: "Stop",
        additionalContext: $msg
    }
}'
exit 0
