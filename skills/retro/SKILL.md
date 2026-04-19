---
description: >
  Run an interactive session retrospective powered by claude-mem. Walks through
  key moments from your session and writes structured memory entries capturing
  decisions, learnings, and rationale. Suggest this when a session has involved
  significant work — debugging, architecture decisions, approach changes, or
  error resolution. Do not suggest for quick Q&A sessions.
  Triggers: "retro", "session summary", "what did we learn", "lessons learned",
  "session retrospective".
---

# Session Retrospective

You are running an interactive session retrospective. Your goal is to walk through
the session with the user, understand what happened and why, and write structured
memory entries that will be useful in future sessions.

## Step 1: Get Session Window

Read the session start timestamp:

```bash
cat ${CLAUDE_PLUGIN_DATA}/session-start-*.txt 2>/dev/null | tail -1
```

If no file exists, use 4 hours ago as the start time.

## Step 2: Query claude-mem

Follow claude-mem's 3-layer pattern to keep token cost low:

**Layer 1 — Search index (~50-100 tokens per result):**

Use the `search` MCP tool with:
- `dateStart` = session start timestamp from Step 1
- `project` = current project name
- `limit` = 50

This returns an index of observations. Review it for retro-worthy moments:
decisions, errors, corrections, discoveries, approach changes.

**Layer 2 — Timeline context (only for key observations):**

For 2-3 observations that look most interesting, use the `timeline` MCP tool
with `anchor` = observation ID to get surrounding context.

**Layer 3 — Full detail (only if discussing a specific moment):**

Use `get_observations` with specific IDs only during the conversation if the
user wants to dig into a particular moment. Never bulk-fetch.

**IMPORTANT:** Do NOT skip to Layer 3. The index from Layer 1 is sufficient to
drive the conversation. Layer 2-3 are selective follow-ups, not default behaviour.

## Step 3: Guided Conversation

Walk through the session chronologically. Ask **one question at a time** — do not
batch questions.

Derive your questions from the claude-mem observations. Focus on:

**Decisions** — when the user chose between alternatives:
- "You explored [A] and [B] before choosing [B]. What tipped the decision?"
- "Was there a reason you went with [approach] over the alternatives?"

**Corrections** — when the user corrected your approach:
- "You corrected me when I tried [approach]. What was wrong with my suggestion?"
- "I notice you redirected me from [X] to [Y]. Is that a general rule for this codebase?"

**Errors and fixes** — when something broke and was resolved:
- "You hit [error] and resolved it by [fix]. Was that the right call?"
- "Anything we should remember to avoid this next time?"

**Techniques** — new patterns or approaches used:
- "The pattern you used for [X] — is this standard for this codebase or something new?"

**End with an open question:**
- "Anything else worth remembering? Surprises, gotchas, things that worked unexpectedly well?"

Do NOT ask questions about routine, successful operations. Focus on moments where
learning happened — pivots, failures, decisions, discoveries.

## Step 4: Write Findings

Write to **both** native memory and claude-mem.

### Native memory entries

Write to the project's memory directory using standard frontmatter format:

**Corrections to Claude's behaviour → `feedback` type:**
```markdown
---
name: {short name}
description: {one-line description}
type: feedback
---

{The rule or preference}

**Why:** {The reason the user gave}

**How to apply:** {When/where this applies}
```
Filename: `retro_feedback_{topic}.md`

**Decisions and project context → `project` type:**
```markdown
---
name: {short name}
description: {one-line description}
type: project
---

{The decision or fact}

**Why:** {The motivation}

**How to apply:** {How this shapes future suggestions}
```
Filename: `retro_project_{topic}.md`

**External resources → `reference` type:**
```markdown
---
name: {short name}
description: {one-line description}
type: reference
---

{The resource and what it's useful for}
```
Filename: `retro_reference_{topic}.md`

Update the project's MEMORY.md index. Show the user each entry for confirmation.

### claude-mem observations

claude-mem's hooks will automatically capture the retro conversation as
observations. No explicit write needed — the act of writing memory files and
discussing decisions generates observations that claude-mem picks up.

## Step 5: Cleanup

```bash
touch ${CLAUDE_PLUGIN_DATA}/retro-done-{session_id}.flag
```

## Guidelines

- Ask ONE question at a time. Wait for the response before asking the next.
- Focus on the "why" — decisions, rationale, trade-offs. Not the "what."
- Keep memory entries concise. One entry per distinct learning.
- Only write memories for things genuinely useful in future sessions.
- If the session was routine with no notable decisions, say so. A short
  "clean session, nothing to capture" is fine.
- Never fabricate learnings. If the data doesn't show clear decision points,
  ask the user what they found valuable rather than inventing insights.
