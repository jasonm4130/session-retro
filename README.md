# session-retro

Claude Code plugin for interactive session retrospectives with auto-nudging and memory integration.

## What it does

- **Auto-detects substantial sessions** using a PreToolUse hook that tracks activity (files changed, subagents spawned, git commits)
- **Nudges before exit** by priming Claude to suggest a retro at a natural conversational moment
- **Interactive walkthrough** where Claude leads you through key decisions, corrections, and errors from the session
- **Writes structured memory entries** (feedback, project, reference types) in Claude's standard format so future sessions benefit
- **Recovers decisions on compaction** by extracting key decisions from the full JSONL transcript when context is compacted

## Install

```
/plugin marketplace add jasonmatthew/session-retro
/plugin install session-retro@jasonmatthew-session-retro
```

## Usage

The plugin works in three ways:

### 1. Automatic nudge

After significant work (configurable thresholds), Claude will suggest running a retro before you end the session.

### 2. Manual invocation

```
/session-retro:retro
```

Or just say "retro", "session summary", "what did we learn", or "lessons learned".

### 3. Pending retros

If you skip the retro, the plugin captures session metadata. Next session, it offers to walk through the previous session's retro.

## Configuration

Optional. Create `config.json` in the plugin's data directory to customise:

```json
{
  "sensitivity": "normal",
  "minToolCalls": 5,
  "minDurationMinutes": 10,
  "enabled": true
}
```

Sensitivity levels: `low` (only major sessions), `normal` (default), `high` (most non-trivial sessions).

## Requirements

- Claude Code >= 2.1.110
- bash 4.0+
- Python 3.10+
- jq

## License

MIT
