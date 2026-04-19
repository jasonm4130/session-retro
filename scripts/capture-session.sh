#!/usr/bin/env bash
# capture-session.sh — SessionEnd hook: fallback retro capture
# Reads session metadata from stdin, writes pending-retro JSON if the session
# was substantial and no retro was already completed.
set -euo pipefail

# ── env ──────────────────────────────────────────────────────────────────────
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugin-data/session-retro}"
mkdir -p "$PLUGIN_DATA"

# ── stdin ─────────────────────────────────────────────────────────────────────
STDIN="$(cat)"

session_id="$(echo "$STDIN"    | jq -r '.session_id        // empty')"
transcript_path="$(echo "$STDIN" | jq -r '.transcript_path  // empty')"
cwd="$(echo "$STDIN"           | jq -r '.cwd               // empty')"
source="$(echo "$STDIN"        | jq -r '.source             // empty')"

if [[ -z "$session_id" ]]; then
  exit 0
fi

# ── skip if retro already done ────────────────────────────────────────────────
RETRO_DONE_FLAG="${PLUGIN_DATA}/retro-done-${session_id}.flag"
if [[ -f "$RETRO_DONE_FLAG" ]]; then
  # Still run cleanup and pruning below
  :
else
  # ── read activity file ──────────────────────────────────────────────────────
  ACTIVITY_FILE="${PLUGIN_DATA}/activity-${session_id}.json"

  if [[ -f "$ACTIVITY_FILE" ]]; then
    activity_json="$(cat "$ACTIVITY_FILE")"
    score="$(echo "$activity_json" | jq -r '.score // 0')"
    started_at="$(echo "$activity_json" | jq -r '.startedAt // ""')"
  else
    activity_json='{}'
    score=0
    started_at=""
  fi

  ended_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  # ── write pending-retro if score > 0 ───────────────────────────────────────
  if [[ "$score" -gt 0 ]] 2>/dev/null; then
    # Best-effort git diff stat from cwd
    git_diff_stat=""
    if [[ -n "$cwd" ]] && git -C "$cwd" rev-parse --is-inside-work-tree &>/dev/null; then
      git_diff_stat="$(git -C "$cwd" diff --stat HEAD~1 HEAD 2>/dev/null | tail -1 || true)"
    fi

    PENDING_FILE="${PLUGIN_DATA}/pending-retro-${session_id}.json"
    jq -n \
      --arg sessionId      "$session_id" \
      --arg transcriptPath "$transcript_path" \
      --arg cwd_val        "$cwd" \
      --arg startedAt      "$started_at" \
      --arg endedAt        "$ended_at" \
      --arg exitReason     "$source" \
      --arg gitDiffStat    "$git_diff_stat" \
      --argjson activity   "$activity_json" \
      '{
        sessionId:      $sessionId,
        transcriptPath: $transcriptPath,
        cwd:            $cwd_val,
        startedAt:      $startedAt,
        endedAt:        $endedAt,
        exitReason:     $exitReason,
        activity:       $activity,
        gitDiffStat:    $gitDiffStat
      }' > "$PENDING_FILE"
  fi
fi

# ── cleanup session-scoped files ──────────────────────────────────────────────
ACTIVITY_FILE="${PLUGIN_DATA}/activity-${session_id}.json"
NUDGE_FLAG="${PLUGIN_DATA}/nudge-sent-${session_id}.flag"

[[ -f "$ACTIVITY_FILE" ]] && rm -f "$ACTIVITY_FILE"
[[ -f "$NUDGE_FLAG"    ]] && rm -f "$NUDGE_FLAG"

# ── prune stale flags / pending retros (>30 days) ────────────────────────────
find "$PLUGIN_DATA" -name "retro-done-*.flag"   -mtime +30 -delete 2>/dev/null || true
find "$PLUGIN_DATA" -name "pending-retro-*.json" -mtime +30 -delete 2>/dev/null || true

exit 0
