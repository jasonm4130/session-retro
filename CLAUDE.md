# Session Retro — Claude Code Plugin

## What this is

A Claude Code plugin that automatically nudges developers to do interactive session retrospectives before ending productive sessions, then writes structured memory entries capturing decisions, learnings, and rationale.

## Key differentiators from existing retro tools

1. **Auto-nudge** — PreToolUse hook detects substantial sessions and primes Claude to suggest a retro naturally
2. **Memory integration** — writes directly to Claude's memory system (feedback, project, reference types)
3. **Full context capture** — reads JSONL transcripts directly, not just what survived compaction
4. **Compaction recovery** — SessionStart(compact) hook extracts decisions after compaction, injects summary into fresh context
5. **Interactive** — guided walkthrough with the user, not a data dump

## Plugin structure

```
session-retro/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── retro/
│       └── SKILL.md
├── hooks/
│   └── hooks.json
├── scripts/
│   ├── track-activity.sh          # PreToolUse — lightweight activity tracker + one-time nudge
│   ├── extract-on-compact.py      # SessionStart(compact) — extract decisions after compaction
│   └── capture-session.sh         # SessionEnd — fallback metadata capture
├── bin/
│   └── session-retro-parse        # JSONL parser utility
└── README.md
```

## Development workflow

- Test locally: `claude --plugin-dir ./`
- Reload after changes: `/reload-plugins`
- Run tests: `npm test` or `python -m pytest`
- Hook scripts receive JSON on stdin — test with: `echo '{"session_id":"test"}' | ./scripts/track-activity.sh`

## Technical constraints

- PreToolUse hooks must be fast (<100ms) — they fire on every tool call
- PreToolUse additionalContext accumulates permanently in context — inject ONCE per session, keep it short (<500 chars)
- Hook output injected into context is capped at 10,000 characters
- PostToolUse `additionalContext` is unreliable for built-in tools (GitHub #18427) — use PreToolUse instead
- PreCompact hook is broken for auto-compaction (bug #50467) — use SessionStart(compact) instead
- Session JSONL files have no locks, safe to read concurrently
- Transcript path derivable from: `~/.claude/projects/{encoded_cwd}/{session_id}.jsonl`
- $CLAUDE_PLUGIN_DATA is persistent across plugin updates, available in hooks as env var

## Conventions

- Shell scripts: bash 4.0+, use `jq` for JSON parsing
- Python scripts: 3.10+, stdlib only (no pip dependencies)
- All scripts must handle missing/malformed input gracefully (exit 0, not crash)
- Memory entries follow the frontmatter format: name, description, type + markdown body
