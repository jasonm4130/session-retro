# session-retro

Claude Code plugin for interactive session retrospectives with auto-nudging and memory integration.

## Why

At the end of a productive Claude Code session, you've made decisions, hit errors, changed approach, discovered patterns — and none of it gets captured. You close the terminal and it's gone. The next session starts from scratch.

Existing retro tools ([accidentalrebel](https://github.com/accidentalrebel/claude-skill-session-retrospective), [bitwarden](https://github.com/bitwarden/ai-plugins/tree/main/plugins/claude-retrospective)) require manual invocation — and nobody remembers to run them. They produce markdown narratives but don't feed back into Claude's memory system. And if compaction has already run, the critical "why we chose X over Y" reasoning is gone.

session-retro fixes all three problems.

## What it does

- **Auto-detects substantial sessions** — a PreToolUse hook tracks activity (files changed, subagents spawned, git commits) and primes Claude to suggest a retro at a natural conversational moment
- **Interactive walkthrough** — Claude leads you through key decisions, corrections, and errors, asking one question at a time
- **Writes structured memory entries** — feedback, project, and reference types in Claude's standard format so future sessions benefit automatically
- **Recovers decisions on compaction** — a SessionStart(compact) hook extracts key decisions from the full JSONL transcript before they're lost

## How it works

Three hooks and one skill:

| Component | Hook event | What it does |
|---|---|---|
| `track-activity.sh` | PreToolUse | Counts tool calls, file changes, subagents, commits. Once a weighted score threshold is met, injects a one-time `additionalContext` nudge — Claude sees it silently and suggests the retro naturally |
| `extract-on-compact.py` | SessionStart (compact) | After compaction, reads the full JSONL (still on disk), extracts decision signals via heuristic pattern matching, writes a memory entry, and injects a summary into the fresh context |
| `capture-session.sh` | SessionEnd | If no retro was done, captures session metadata so the next session can offer a pending retro |
| `/session-retro:retro` | Skill | The interactive guided walkthrough — parses the session transcript, asks targeted questions about decisions/errors/corrections, writes memory entries |

The nudge fires once per session, only after minimum thresholds are met. No context flooding, no forced continuation — Claude suggests it at the right moment and you can decline.

## Install

```
/plugin marketplace add jasonm4130/session-retro
/plugin install session-retro@jasonm4130-session-retro
/reload-plugins
```

On first load, Claude Code will prompt you to approve the plugin's hooks (PreToolUse, SessionStart, SessionEnd). This is normal — plugins that execute code require explicit user trust. Approve to enable auto-nudging and session capture.

## Usage

### Automatic nudge

After significant work (configurable thresholds), Claude will suggest running a retro before you end the session. No action needed — just work normally.

### Manual invocation

```
/session-retro:retro
```

Or say "retro", "session summary", "what did we learn", or "lessons learned".

### Pending retros

If you skip the retro, the plugin captures session metadata. Next session, it offers to walk through the previous session's learnings. The JSONL transcript is still on disk, so the full context is available.

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

| Sensitivity | Behaviour |
|---|---|
| `low` | Only nudge for clearly significant sessions (long debugging, major architecture decisions) |
| `normal` | Nudge when meaningful work happened (default) |
| `high` | Nudge for most non-trivial sessions |

## Requirements

- Claude Code >= 2.1.110
- bash 4.0+
- Python 3.10+ (stdlib only, no pip dependencies)
- jq

## License

MIT
