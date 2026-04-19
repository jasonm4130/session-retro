"""Heuristic decision signal extraction from parsed session timelines."""

import re

DECISION_PATTERNS = [
    r"(?i)\blet'?s go with\b",
    r"(?i)\bwe should\b",
    r"(?i)\bi think we should\b",
    r"(?i)\bthe trade-?off is\b",
    r"(?i)\bi'?d prefer\b",
    r"(?i)\blet'?s use\b",
    r"(?i)\bwe'?ll use\b",
    r"(?i)\bi decided\b",
    r"(?i)\bthe decision is\b",
    r"(?i)\bgo ahead with\b",
]


def extract_decisions(timeline: list[dict]) -> list[dict]:
    """Extract decision signals from a parsed session timeline.

    Returns list of dicts with keys: signal, timestamp, detail
    """
    decisions = []

    for i, event in enumerate(timeline):
        if event["type"] == "user_correction":
            decisions.append({
                "signal": "correction",
                "timestamp": event.get("timestamp", ""),
                "detail": event.get("raw", event.get("summary", ""))[:300],
            })

        elif event["type"] == "error":
            fix = _find_fix_after(timeline, i)
            if fix:
                decisions.append({
                    "signal": "error_fix",
                    "timestamp": event.get("timestamp", ""),
                    "detail": f"Error in {event.get('tool', '?')}: "
                              f"{event.get('error', '')[:200]} → "
                              f"Fixed via {fix['tool']} on {fix.get('target', '?')}",
                })

        elif event["type"] == "user_message":
            raw = event.get("raw", "")
            if _is_explicit_decision(raw):
                decisions.append({
                    "signal": "explicit_decision",
                    "timestamp": event.get("timestamp", ""),
                    "detail": raw[:300],
                })

    return decisions


def _find_fix_after(timeline: list[dict], error_index: int) -> dict | None:
    for j in range(error_index + 1, min(error_index + 4, len(timeline))):
        event = timeline[j]
        if event["type"] == "tool_call" and event.get("success"):
            if event.get("tool") in ("Write", "Edit", "Bash"):
                return event
    return None


def _is_explicit_decision(text: str) -> bool:
    for pattern in DECISION_PATTERNS:
        if re.search(pattern, text):
            return True
    return False
