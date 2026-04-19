"""JSONL session parser — core timeline extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Patterns that indicate a user is correcting the assistant.
_CORRECTION_PATTERNS = [
    re.compile(r"^no[,.]?\s", re.IGNORECASE),
    re.compile(r"\bdon'?t\b.*\binstead\b", re.IGNORECASE),
    re.compile(r"\bwrong\b", re.IGNORECASE),
    re.compile(r"\bnot that\b", re.IGNORECASE),
    re.compile(r"\bwe can'?t use\b", re.IGNORECASE),
    re.compile(r"\bswitch to\b", re.IGNORECASE),
]

# Pattern to extract commit message from git commit output.
# Matches: [branch hash] message
_GIT_COMMIT_MSG_RE = re.compile(r"\] (.+?)(?:\n|$)")


def parse_session(
    jsonl_path: str | Path,
    condensed: bool = False,
    include_subagents: bool = False,
) -> dict:
    """Parse a Claude Code session JSONL file into a structured timeline.

    Args:
        jsonl_path: Path to the .jsonl session file.
        condensed: If True, return a condensed timeline (fewer tool_call entries).
        include_subagents: If True, inline subagent summaries from meta.json files.

    Returns:
        Dict with sessionId, startedAt, endedAt, cwd, version, gitBranch,
        timeline (list of events), and stats.
    """
    jsonl_path = Path(jsonl_path)
    lines = _load_lines(jsonl_path)

    session_id = ""
    cwd = ""
    version = ""
    git_branch = ""
    started_at = ""
    ended_at = ""

    timeline: list[dict[str, Any]] = []
    # Map tool_use_id -> pending tool info from assistant messages
    pending_tools: dict[str, dict[str, Any]] = {}

    for line in lines:
        line_type = line.get("type")

        if line_type == "permission-mode":
            session_id = line.get("sessionId", session_id)
            continue

        if line_type == "user":
            msg = line.get("message", {})
            content = msg.get("content")
            timestamp = line.get("timestamp", "")

            # Extract metadata from the first external user message
            if line.get("userType") == "external" and not cwd:
                cwd = line.get("cwd", "")
                version = line.get("version", "")
                git_branch = line.get("gitBranch", "")

            # Track timestamps for startedAt / endedAt
            if timestamp:
                if not started_at:
                    started_at = timestamp
                ended_at = timestamp

            if isinstance(content, str):
                # Plain text user message
                event: dict[str, Any] = {
                    "type": "user_message",
                    "timestamp": timestamp,
                    "raw": content,
                }
                # Check if this is a correction
                if _is_correction(content):
                    event["type"] = "user_correction"
                timeline.append(event)

            elif isinstance(content, list):
                # Tool result(s) — match to pending tool_use blocks
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_result":
                        continue
                    tool_use_id = block.get("tool_use_id", "")
                    result_text = block.get("content", "")
                    is_error = block.get("is_error", False)

                    pending = pending_tools.pop(tool_use_id, None)
                    if pending is None:
                        continue

                    tool_name = pending["name"]
                    tool_input = pending.get("input", {})
                    tool_timestamp = pending["timestamp"]

                    # Build the tool_call event
                    tc_event: dict[str, Any] = {
                        "type": "tool_call",
                        "timestamp": tool_timestamp,
                        "tool": tool_name,
                        "success": not is_error,
                    }

                    # Extract target for file-oriented tools
                    target = _extract_target(tool_name, tool_input)
                    if target:
                        tc_event["target"] = target

                    # Check for overflow / persisted-output
                    if isinstance(result_text, str) and "<persisted-output>" in result_text:
                        tc_event["overflow"] = True
                        overflow_match = re.search(
                            r"<persisted-output\s+path=\"([^\"]+)\"", result_text
                        )
                        if overflow_match:
                            tc_event["overflowPath"] = overflow_match.group(1)

                    # Agent / subagent detection
                    if tool_name == "Agent":
                        tc_event["type"] = "subagent"
                        tc_event["prompt"] = tool_input.get("prompt", "")
                        tc_event["description"] = tool_input.get("description", "")
                        tc_event["subagentType"] = tool_input.get("subagent_type", "")

                    timeline.append(tc_event)

                    # Error event
                    if is_error:
                        timeline.append({
                            "type": "error",
                            "timestamp": timestamp,
                            "tool": tool_name,
                            "error": result_text if isinstance(result_text, str) else str(result_text),
                        })

                    # Git commit detection
                    if (
                        tool_name == "Bash"
                        and isinstance(tool_input.get("command"), str)
                        and "git commit" in tool_input["command"]
                        and not is_error
                    ):
                        commit_msg = _extract_commit_message(
                            result_text if isinstance(result_text, str) else ""
                        )
                        if commit_msg:
                            timeline.append({
                                "type": "git_commit",
                                "timestamp": timestamp,
                                "message": commit_msg,
                            })

        elif line_type == "assistant":
            msg = line.get("message", {})
            content = msg.get("content", [])
            timestamp = line.get("timestamp", "")

            if timestamp:
                if not started_at:
                    started_at = timestamp
                ended_at = timestamp

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        tool_use_id = block.get("id", "")
                        pending_tools[tool_use_id] = {
                            "name": block.get("name", ""),
                            "input": block.get("input", {}),
                            "timestamp": timestamp,
                        }

    # Sort timeline chronologically
    timeline.sort(key=lambda e: e.get("timestamp", ""))

    # Load subagent summaries if requested
    if include_subagents:
        timeline = _load_subagent_summaries(jsonl_path, timeline)

    # Condense if requested
    if condensed:
        timeline = _condense_timeline(timeline)

    # Compute stats
    stats = _compute_stats(timeline)

    return {
        "sessionId": session_id,
        "startedAt": started_at,
        "endedAt": ended_at,
        "cwd": cwd,
        "version": version,
        "gitBranch": git_branch,
        "timeline": timeline,
        "stats": stats,
    }


def _load_lines(jsonl_path: Path) -> list[dict]:
    """Load and parse all JSON lines from a file."""
    lines = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                lines.append(json.loads(raw_line))
            except json.JSONDecodeError:
                continue
    return lines


def _is_correction(text: str) -> bool:
    """Check if a user message is correcting the assistant."""
    for pattern in _CORRECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _extract_target(tool_name: str, tool_input: dict) -> str:
    """Extract the target file path from a tool call's input."""
    if tool_name in ("Write", "Read", "Edit"):
        return tool_input.get("file_path", "")
    return ""


def _extract_commit_message(result_text: str) -> str:
    """Extract commit message from git commit output."""
    match = _GIT_COMMIT_MSG_RE.search(result_text)
    if match:
        return match.group(1).strip()
    return ""


def _compute_stats(timeline: list[dict]) -> dict:
    """Compute summary statistics from the timeline."""
    tool_calls = 0
    errors = 0
    corrections = 0
    subagents = 0
    git_commits = 0
    files_changed: set[str] = set()

    for event in timeline:
        etype = event.get("type")
        if etype == "tool_call":
            tool_calls += 1
            target = event.get("target", "")
            tool = event.get("tool", "")
            if target and tool in ("Write", "Edit"):
                files_changed.add(target)
        elif etype == "error":
            errors += 1
        elif etype == "user_correction":
            corrections += 1
        elif etype == "subagent":
            subagents += 1
        elif etype == "git_commit":
            git_commits += 1

    return {
        "toolCalls": tool_calls,
        "errors": errors,
        "corrections": corrections,
        "subagents": subagents,
        "gitCommits": git_commits,
        "filesChanged": sorted(files_changed),
    }


def _condense_timeline(timeline: list[dict]) -> list[dict]:
    """Condense timeline: keep key events plus first/last tool_call per file.

    Keeps: user_message, user_correction, error, subagent, git_commit,
    plus the first and last tool_call for each target file.
    """
    keep_types = {"user_message", "user_correction", "error", "subagent", "git_commit"}
    condensed = []
    # Track first and last tool_call per target
    first_by_target: dict[str, dict] = {}
    last_by_target: dict[str, dict] = {}

    for event in timeline:
        if event["type"] in keep_types:
            condensed.append(event)
        elif event["type"] == "tool_call":
            target = event.get("target", event.get("tool", "__no_target__"))
            if target not in first_by_target:
                first_by_target[target] = event
            last_by_target[target] = event

    # Add first/last tool calls
    for target, first in first_by_target.items():
        condensed.append(first)
        last = last_by_target[target]
        if last is not first:
            condensed.append(last)

    # Re-sort chronologically
    condensed.sort(key=lambda e: e.get("timestamp", ""))
    return condensed


def _load_subagent_summaries(
    jsonl_path: Path, timeline: list[dict]
) -> list[dict]:
    """Load subagent meta.json summaries and attach to subagent events.

    Looks for a sibling subagents/ directory containing *.meta.json files.
    """
    subagents_dir = jsonl_path.parent / "subagents"
    if not subagents_dir.is_dir():
        return timeline

    meta_files = {}
    for meta_path in subagents_dir.glob("*.meta.json"):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_files[meta_path.stem] = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

    # Attach metadata to subagent events
    for event in timeline:
        if event.get("type") == "subagent":
            for _, meta in meta_files.items():
                if meta.get("agentType") == event.get("subagentType"):
                    event["meta"] = meta
                    break

    return timeline
