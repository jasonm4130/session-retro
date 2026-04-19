"""Tests for heuristic decision signal extraction."""

from lib.decisions import extract_decisions


class TestExtractDecisions:
    def test_extracts_corrections(self):
        timeline = [
            {"type": "user_correction", "timestamp": "t1",
             "raw": "No, we can't use cookies because of the CDN. Use bearer tokens.",
             "summary": "Don't use cookies, use bearer tokens"},
        ]
        decisions = extract_decisions(timeline)
        assert len(decisions) >= 1
        assert any("cookie" in d["detail"].lower() or "bearer" in d["detail"].lower()
                    for d in decisions)

    def test_extracts_error_fix_sequences(self):
        timeline = [
            {"type": "error", "timestamp": "t1", "tool": "Bash",
             "error": "TypeError: Cannot read properties of undefined"},
            {"type": "tool_call", "timestamp": "t2", "tool": "Edit",
             "target": "src/auth.ts", "success": True},
        ]
        decisions = extract_decisions(timeline)
        assert any(d["signal"] == "error_fix" for d in decisions)

    def test_extracts_explicit_decisions_from_user_messages(self):
        timeline = [
            {"type": "user_message", "timestamp": "t1",
             "raw": "Let's go with jose over jsonwebtoken for the JWT library"},
        ]
        decisions = extract_decisions(timeline)
        assert any(d["signal"] == "explicit_decision" for d in decisions)

    def test_empty_timeline_returns_empty(self):
        assert extract_decisions([]) == []

    def test_routine_session_returns_few_decisions(self):
        timeline = [
            {"type": "user_message", "timestamp": "t1", "raw": "Add a hello endpoint"},
            {"type": "tool_call", "timestamp": "t2", "tool": "Write",
             "target": "src/index.ts", "success": True},
            {"type": "user_message", "timestamp": "t3", "raw": "Thanks!"},
        ]
        decisions = extract_decisions(timeline)
        assert len(decisions) <= 1
