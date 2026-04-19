"""Tests for JSONL session parser."""

import json
from pathlib import Path

from lib.parser import parse_session


class TestParseSession:
    """Test core timeline extraction from JSONL."""

    def test_extracts_session_metadata(self, fixtures_dir):
        result = parse_session(fixtures_dir / "small_session.jsonl")
        assert result["sessionId"] == "small-001"
        assert result["cwd"] == "/tmp/test-project"
        assert result["version"] == "2.1.112"
        assert result["gitBranch"] == "main"
        assert result["startedAt"] == "2026-04-19T10:00:00.000Z"
        assert result["endedAt"] == "2026-04-19T10:02:30.000Z"

    def test_extracts_user_messages(self, fixtures_dir):
        result = parse_session(fixtures_dir / "small_session.jsonl")
        user_msgs = [e for e in result["timeline"] if e["type"] == "user_message"]
        assert len(user_msgs) == 2
        assert user_msgs[0]["raw"] == "Add a hello world endpoint"
        assert user_msgs[1]["raw"] == "Thanks!"

    def test_extracts_tool_calls(self, fixtures_dir):
        result = parse_session(fixtures_dir / "small_session.jsonl")
        tool_calls = [e for e in result["timeline"] if e["type"] == "tool_call"]
        assert len(tool_calls) == 4
        assert tool_calls[0]["tool"] == "Write"
        assert tool_calls[0]["target"] == "src/index.ts"
        assert tool_calls[0]["success"] is True

    def test_extracts_git_commits(self, fixtures_dir):
        result = parse_session(fixtures_dir / "small_session.jsonl")
        commits = [e for e in result["timeline"] if e["type"] == "git_commit"]
        assert len(commits) == 1
        assert "hello endpoint" in commits[0]["message"]

    def test_computes_stats(self, fixtures_dir):
        result = parse_session(fixtures_dir / "small_session.jsonl")
        stats = result["stats"]
        assert stats["toolCalls"] == 4
        assert stats["errors"] == 0
        assert stats["corrections"] == 0
        assert stats["gitCommits"] == 1
        assert "src/index.ts" in stats["filesChanged"]
        assert "src/index.test.ts" in stats["filesChanged"]

    def test_extracts_errors(self, fixtures_dir):
        result = parse_session(fixtures_dir / "session_with_errors.jsonl")
        errors = [e for e in result["timeline"] if e["type"] == "error"]
        assert len(errors) == 1
        assert "TypeError" in errors[0]["error"]
        assert errors[0]["tool"] == "Bash"

    def test_extracts_user_corrections(self, fixtures_dir):
        result = parse_session(fixtures_dir / "session_with_errors.jsonl")
        corrections = [e for e in result["timeline"] if e["type"] == "user_correction"]
        assert len(corrections) == 1
        assert "cookies" in corrections[0]["raw"].lower()

    def test_error_stats(self, fixtures_dir):
        result = parse_session(fixtures_dir / "session_with_errors.jsonl")
        assert result["stats"]["errors"] == 1
        assert result["stats"]["corrections"] == 1

    def test_timeline_is_chronological(self, fixtures_dir):
        result = parse_session(fixtures_dir / "small_session.jsonl")
        timestamps = [e["timestamp"] for e in result["timeline"]]
        assert timestamps == sorted(timestamps)
