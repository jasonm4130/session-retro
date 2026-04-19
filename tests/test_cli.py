"""Tests for session-retro-parse CLI."""

import json
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).parent.parent / "bin" / "session-retro-parse"


def run_parser(*args: str) -> subprocess.CompletedProcess:
    """Run the CLI parser and return the result."""
    return subprocess.run(
        [sys.executable, str(BIN), *args],
        capture_output=True,
        text=True,
    )


class TestCLI:
    def test_parses_session_to_stdout(self, fixtures_dir):
        result = run_parser(str(fixtures_dir / "small_session.jsonl"))
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["sessionId"] == "small-001"
        assert len(data["timeline"]) > 0
        assert "stats" in data

    def test_condensed_flag(self, fixtures_dir):
        result = run_parser(
            str(fixtures_dir / "small_session.jsonl"), "--condensed"
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "timeline" in data

    def test_include_subagents_flag(self, fixtures_dir):
        result = run_parser(
            str(fixtures_dir / "session_with_subagents" / "main.jsonl"),
            "--include-subagents",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        subagents = [e for e in data["timeline"] if e["type"] == "subagent"]
        assert len(subagents) >= 1

    def test_missing_file_exits_nonzero(self):
        result = run_parser("/nonexistent/file.jsonl")
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "not found" in result.stderr.lower()

    def test_no_args_shows_usage(self):
        result = run_parser()
        assert result.returncode != 0
