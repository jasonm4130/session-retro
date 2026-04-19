#!/usr/bin/env python3
"""SessionStart(compact) hook: extract decisions from JSONL after compaction."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add plugin root to path
plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root))

from lib.parser import parse_session
from lib.decisions import extract_decisions
from lib.memory import write_memory_entry, update_memory_index


def main():
    try:
        stdin_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = stdin_data.get("transcript_path", "")
    if not transcript_path or not Path(transcript_path).exists():
        sys.exit(0)

    # Parse session
    try:
        session = parse_session(transcript_path, condensed=True)
    except Exception:
        sys.exit(0)

    # Extract decisions
    decisions = extract_decisions(session.get("timeline", []))
    if not decisions:
        sys.exit(0)

    # Derive memory directory from transcript path
    # Pattern: ~/.claude/projects/{encoded_cwd}/{session_id}.jsonl
    transcript = Path(transcript_path)
    project_dir = transcript.parent
    memory_dir = project_dir / "memory"

    # Write memory entry
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"compact_extract_{timestamp}.md"

    body_lines = ["Decisions and context extracted before compaction:\n"]
    for d in decisions[:20]:  # Cap at 20
        body_lines.append(f"- **{d['signal']}**: {d['detail']}")

    body = "\n".join(body_lines)

    write_memory_entry(
        memory_dir=memory_dir,
        filename=filename,
        name=f"Compaction extract ({timestamp})",
        description=f"Decisions recovered from session before compaction — {len(decisions)} signals",
        memory_type="project",
        body=body,
    )

    update_memory_index(
        memory_dir=memory_dir,
        filename=filename,
        description=f"Compaction extract ({timestamp}) — {len(decisions)} decisions",
    )

    # Return additionalContext (max 2000 chars)
    summary_lines = ["Pre-compaction decisions recovered:"]
    char_count = len(summary_lines[0])
    for d in decisions:
        line = f"\n- {d['detail'][:150]}"
        if char_count + len(line) > 1900:
            summary_lines.append(f"\n- ...and {len(decisions) - len(summary_lines) + 1} more (see memory)")
            break
        summary_lines.append(line)
        char_count += len(line)

    summary = "".join(summary_lines)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": summary,
        }
    }
    json.dump(output, sys.stdout)
    print()


if __name__ == "__main__":
    main()
