# session-retro

Claude Code plugin for interactive session retrospectives, powered by [claude-mem](https://github.com/thedotmack/claude-mem).

## Why

At the end of a productive Claude Code session, you've made decisions, hit errors, changed approach, discovered patterns — and none of it gets captured in a way that helps future sessions. You close the terminal and the reasoning is gone.

Existing retro tools ([accidentalrebel](https://github.com/accidentalrebel/claude-skill-session-retrospective), [bitwarden](https://github.com/bitwarden/ai-plugins/tree/main/plugins/claude-retrospective)) parse raw JSONL transcripts at retro time — expensive in tokens and backwards. claude-mem already captures observations continuously in the background. session-retro reads from that, not from raw transcripts.

## What it does

- **Reads from claude-mem** — queries session observations using the 3-layer search pattern (~1,500-3,000 tokens instead of 37,000+ for raw JSONL)
- **Guided walkthrough** — walks through key decisions, corrections, and errors one question at a time
- **Writes to both systems** — native memory entries (project-scoped, Claude reads automatically) and claude-mem observations (cross-project, searchable)
- **Auto-suggests** — Claude knows to suggest a retro when a session has been substantial. No hooks needed for nudging.

## How it works

One hook and one skill:

| Component | What it does |
|---|---|
| `mark-session-start.sh` | SessionStart hook — writes a timestamp so the skill knows where this session begins in claude-mem's observations |
| `/session-retro:retro` | Queries claude-mem for this session's observations, walks through key moments with you, writes memory entries |

## Install

**Requires [claude-mem](https://github.com/thedotmack/claude-mem) to be installed first.**

```
/plugin marketplace add jasonm4130/session-retro
/plugin install session-retro@jasonm4130-session-retro
/reload-plugins
```

On first load, Claude Code will prompt you to approve the SessionStart hook. This is normal — plugins that execute code require explicit user trust.

## Usage

### Automatic suggestion

After significant work, Claude will suggest running a retro. No action needed — just work normally.

### Manual invocation

```
/session-retro:retro
```

Claude also picks up natural language — "retro", "what did we learn", "session summary" all trigger it.

## Requirements

- [claude-mem](https://github.com/thedotmack/claude-mem) plugin
- Claude Code >= 2.1.110
- bash

## License

MIT
