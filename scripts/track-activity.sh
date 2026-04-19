#!/usr/bin/env bash
set -euo pipefail

# PreToolUse hook: track session activity and nudge for retro when thresholds met.
# Must complete in <100ms — no heavy operations.

# Read all stdin at once
INPUT=$(cat)

# Extract fields from stdin JSON
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')

# Bail gracefully if no session_id
if [[ -z "${SESSION_ID:-}" ]]; then
  exit 0
fi

# Ensure plugin data directory exists
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-}"
if [[ -z "$PLUGIN_DATA" ]]; then
  exit 0
fi
mkdir -p "$PLUGIN_DATA"

ACTIVITY_FILE="$PLUGIN_DATA/activity-${SESSION_ID}.json"
FLAG_FILE="$PLUGIN_DATA/nudge-sent-${SESSION_ID}.flag"
CONFIG_FILE="$PLUGIN_DATA/config.json"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

# --- Create or update activity file ---

if [[ -f "$ACTIVITY_FILE" ]]; then
  ACTIVITY=$(cat "$ACTIVITY_FILE")
else
  # Initialize new activity file
  ACTIVITY=$(jq -n \
    --arg sid "$SESSION_ID" \
    --arg tp "${TRANSCRIPT_PATH:-}" \
    --arg cwd "${CWD:-}" \
    --arg now "$NOW" \
    '{
      sessionId: $sid,
      transcriptPath: $tp,
      cwd: $cwd,
      firstSeenAt: $now,
      lastSeenAt: $now,
      toolCalls: 0,
      filesChanged: [],
      subagentsSpawned: 0,
      gitCommits: 0,
      score: 0
    }')
fi

# Always increment toolCalls and update lastSeenAt
ACTIVITY=$(echo "$ACTIVITY" | jq --arg now "$NOW" '
  .toolCalls += 1 |
  .lastSeenAt = $now
')

# Track file changes for Write/Edit tools
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
  FILE_PATH=$(echo "$TOOL_INPUT" | jq -r '.file_path // empty')
  if [[ -n "$FILE_PATH" ]]; then
    ACTIVITY=$(echo "$ACTIVITY" | jq --arg fp "$FILE_PATH" '
      if (.filesChanged | index($fp)) then . else .filesChanged += [$fp] end
    ')
  fi
fi

# Track subagent spawns
if [[ "$TOOL_NAME" == "Agent" ]]; then
  ACTIVITY=$(echo "$ACTIVITY" | jq '.subagentsSpawned += 1')
fi

# Track git commits
if [[ "$TOOL_NAME" == "Bash" ]]; then
  COMMAND=$(echo "$TOOL_INPUT" | jq -r '.command // empty')
  if [[ "$COMMAND" == *"git commit"* ]]; then
    ACTIVITY=$(echo "$ACTIVITY" | jq '.gitCommits += 1')
  fi
fi

# Recalculate score: (filesChanged_count * 2) + (subagentsSpawned * 2) + (gitCommits * 1)
ACTIVITY=$(echo "$ACTIVITY" | jq '
  .score = ((.filesChanged | length) * 2) + (.subagentsSpawned * 2) + (.gitCommits * 1)
')

# Write activity file
echo "$ACTIVITY" > "$ACTIVITY_FILE"

# --- Nudge logic ---

# Don't nudge if flag already set (already nudged this session)
if [[ -f "$FLAG_FILE" ]]; then
  exit 0
fi

# Check if plugin is enabled via config
if [[ -f "$CONFIG_FILE" ]]; then
  ENABLED=$(jq -r '.enabled // true' "$CONFIG_FILE")
  if [[ "$ENABLED" == "false" ]]; then
    exit 0
  fi
fi

# Read thresholds from config or use defaults
if [[ -f "$CONFIG_FILE" ]]; then
  MIN_TOOL_CALLS=$(jq -r '.minToolCalls // 5' "$CONFIG_FILE")
  MIN_DURATION=$(jq -r '.minDurationMinutes // 10' "$CONFIG_FILE")
  SENSITIVITY=$(jq -r '.sensitivity // "normal"' "$CONFIG_FILE")
else
  MIN_TOOL_CALLS=5
  MIN_DURATION=10
  SENSITIVITY="normal"
fi

# Determine score threshold based on sensitivity
case "$SENSITIVITY" in
  low)  SCORE_THRESHOLD=15 ;;
  high) SCORE_THRESHOLD=3 ;;
  *)    SCORE_THRESHOLD=8 ;;  # normal default
esac

# Check if config overrides the threshold for the sensitivity level
if [[ -f "$CONFIG_FILE" ]]; then
  CUSTOM_THRESHOLD=$(jq -r ".thresholds.${SENSITIVITY} // empty" "$CONFIG_FILE")
  if [[ -n "$CUSTOM_THRESHOLD" ]]; then
    SCORE_THRESHOLD="$CUSTOM_THRESHOLD"
  fi
fi

# Extract current values
TOOL_CALLS=$(echo "$ACTIVITY" | jq -r '.toolCalls')
SCORE=$(echo "$ACTIVITY" | jq -r '.score')
FILES_COUNT=$(echo "$ACTIVITY" | jq -r '.filesChanged | length')
FIRST_SEEN=$(echo "$ACTIVITY" | jq -r '.firstSeenAt')

# Check minToolCalls
if (( TOOL_CALLS < MIN_TOOL_CALLS )); then
  exit 0
fi

# Check elapsed time
# Parse firstSeenAt ISO timestamp to epoch seconds
# macOS date: use -j -f format
# Strip fractional seconds for parsing
FIRST_SEEN_TRIMMED="${FIRST_SEEN%%.*}"

if command -v gdate &>/dev/null; then
  FIRST_EPOCH=$(gdate -d "$FIRST_SEEN_TRIMMED" +%s 2>/dev/null || echo 0)
else
  FIRST_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$FIRST_SEEN_TRIMMED" +%s 2>/dev/null || echo 0)
fi

NOW_EPOCH=$(date +%s)
ELAPSED_SECONDS=$(( NOW_EPOCH - FIRST_EPOCH ))
ELAPSED_MIN=$(( ELAPSED_SECONDS / 60 ))

if (( ELAPSED_MIN < MIN_DURATION )); then
  exit 0
fi

# Check score threshold
if (( SCORE < SCORE_THRESHOLD )); then
  exit 0
fi

# All conditions met — emit nudge and set flag
touch "$FLAG_FILE"

cat <<NUDGE_EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Session activity: significant work detected (score ${SCORE}, ${FILES_COUNT} files changed, ${ELAPSED_MIN}min). When the user's current task is complete, suggest /session-retro:retro to capture learnings. Do not interrupt active work."}}
NUDGE_EOF

exit 0
