---
description: >
  Run an interactive session retrospective. Analyzes your current session transcript,
  walks through key moments with you, and writes structured memory entries capturing
  decisions, learnings, and rationale.
  Use when: "retro", "session summary", "what did we learn", "lessons learned",
  "session retrospective", or the user wants to review what happened in a session.
---

# Session Retrospective

You are running an interactive session retrospective. Your goal is to walk through
the session with the user, understand what happened and why, and write structured
memory entries that will be useful in future sessions.

## Step 1: Session Ingestion

First, check for pending retros from previous sessions:

```bash
ls ${CLAUDE_PLUGIN_DATA}/pending-retro-*.json 2>/dev/null
```

If pending retros exist, read them and offer: "I found a pending retro from your
last session ({date}, {duration}, {summary}). Want to review that one too, or
focus on the current session?"

For the current session, parse the transcript using the session-retro-parse tool
(available on PATH via the plugin's bin/ directory).

**IMPORTANT: Only use `--summary` mode.** Never use `--condensed` or full parse — they
dump 30,000+ tokens into context and will blow through the user's token budget.

```bash
session-retro-parse <transcript_path> --summary --include-subagents
```

This returns stats + key moments only (~1,400 tokens). This is all you need to drive
the guided conversation. The key moments contain errors, corrections, commits, and
subagent dispatches — enough to ask targeted questions without the full timeline.

The transcript path is available from the session context. If you cannot determine
it, check `${CLAUDE_PLUGIN_DATA}/activity-*.json` files for the current session's
`transcriptPath` field.

## Step 2: Guided Conversation

Walk through the session chronologically. Ask **one question at a time** — do not
batch questions.

Derive your questions from what actually happened in the parsed timeline. Focus on:

**Decisions** — when the user chose between alternatives:
- "You explored [A] and [B] before choosing [B]. What tipped the decision?"
- "Was there a reason you went with [approach] over the alternatives?"

**Corrections** — when the user corrected your approach:
- "You corrected me when I tried [approach]. What was wrong with my suggestion?"
- "I notice you redirected me from [X] to [Y]. Is that a general rule for this codebase?"

**Errors and fixes** — when something broke and was resolved:
- "You hit [error] and resolved it by [fix]. Was that the right call, or would you approach it differently?"
- "That [error] took [N] attempts to fix. Anything we should remember to avoid it next time?"

**Techniques** — new patterns or approaches used:
- "The pattern you used for [X] — is this standard for this codebase or something new?"
- "You used [tool/technique]. Worth remembering for future sessions?"

**End with an open question:**
- "Anything else that came up that's worth remembering? Surprises, gotchas, things that worked unexpectedly well?"

Do NOT ask questions about routine, successful operations. Focus on moments where
learning happened — pivots, failures, decisions, discoveries.

## Step 3: Memory Generation

Based on the conversation, write memory entries to the project's memory directory.
Use the standard frontmatter format:

### For corrections to your (Claude's) behaviour → `feedback` type

```markdown
---
name: {short name}
description: {one-line description for relevance matching}
type: feedback
---

{The rule or preference}

**Why:** {The reason the user gave}

**How to apply:** {When/where this applies}
```

Filename pattern: `retro_feedback_{topic}.md`

### For decisions and project context → `project` type

```markdown
---
name: {short name}
description: {one-line description for relevance matching}
type: project
---

{The decision or fact}

**Why:** {The motivation — constraint, requirement, trade-off}

**How to apply:** {How this should shape future suggestions}
```

Filename pattern: `retro_project_{topic}.md`

### For external resources discovered → `reference` type

```markdown
---
name: {short name}
description: {one-line description for relevance matching}
type: reference
---

{The resource and what it's useful for}
```

Filename pattern: `retro_reference_{topic}.md`

After writing each entry, update the project's MEMORY.md index with a one-line
pointer. Show the user each entry you wrote so they can confirm or adjust.

## Step 4: Cleanup

After the retro is complete:

1. Write a completion flag:
```bash
touch ${CLAUDE_PLUGIN_DATA}/retro-done-{session_id}.flag
```

2. If you retroed a pending session from a previous session, delete its pending file:
```bash
rm ${CLAUDE_PLUGIN_DATA}/pending-retro-{session_id}.json
```

## Guidelines

- Ask ONE question at a time. Wait for the user's response before asking the next.
- Focus on the "why" — decisions, rationale, trade-offs. Not the "what" (that's in git).
- Keep memory entries concise. One entry per distinct learning, not a mega-document.
- Only write memories for things that are genuinely useful in future sessions.
  "We wrote a function" is not useful. "We chose jose over jsonwebtoken because
  of Web Crypto API support" IS useful.
- If the session was routine with no notable decisions, say so. Not every session
  needs memory entries. A short "clean session, nothing to capture" is fine.
- Never fabricate learnings. If the session data doesn't show clear decision points,
  ask the user what they found valuable rather than inventing insights.
