"""Tests for extract-on-compact.py SessionStart(compact) hook."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "extract-on-compact.py"
FIXTURES = Path(__file__).parent / "fixtures"


def run_hook(stdin_data: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(Path(__file__).parent.parent)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        env=env,
    )


class TestExtractOnCompact:
    def test_extracts_decisions_and_writes_memory(self):
        transcript = FIXTURES / "session_with_errors.jsonl"
        memory_dir = FIXTURES / "memory"
        memory_dir.mkdir(exist_ok=True)
        try:
            result = run_hook({
                "session_id": "errors-001",
                "transcript_path": str(transcript),
                "cwd": "/tmp/test-project",
                "hook_event_name": "SessionStart",
                "source": "compact",
            })
            assert result.returncode == 0

            # A compact_extract_*.md file should exist in memory/
            memory_files = list(memory_dir.glob("compact_extract_*.md"))
            assert len(memory_files) == 1, (
                f"Expected 1 compact_extract_*.md, got {memory_files}"
            )

            content = memory_files[0].read_text()
            # Check frontmatter is present
            assert content.startswith("---\n")
            assert "type: project" in content
            assert "name:" in content
            assert "description:" in content
        finally:
            shutil.rmtree(memory_dir, ignore_errors=True)

    def test_returns_additional_context(self):
        transcript = FIXTURES / "session_with_errors.jsonl"
        memory_dir = FIXTURES / "memory"
        memory_dir.mkdir(exist_ok=True)
        try:
            result = run_hook({
                "session_id": "errors-001",
                "transcript_path": str(transcript),
                "cwd": "/tmp/test-project",
                "hook_event_name": "SessionStart",
                "source": "compact",
            })
            assert result.returncode == 0
            assert result.stdout.strip(), "Expected JSON output on stdout"

            output = json.loads(result.stdout.strip())
            assert "hookSpecificOutput" in output
            hook_out = output["hookSpecificOutput"]
            assert hook_out.get("hookEventName") == "SessionStart"
            additional_context = hook_out.get("additionalContext", "")
            assert additional_context, "additionalContext should not be empty"
            assert len(additional_context) <= 2000, (
                f"additionalContext exceeds 2000 chars: {len(additional_context)}"
            )
        finally:
            shutil.rmtree(memory_dir, ignore_errors=True)

    def test_handles_missing_transcript(self):
        result = run_hook({
            "session_id": "ghost-session",
            "transcript_path": "/nonexistent/path/session.jsonl",
            "cwd": "/tmp/test-project",
            "hook_event_name": "SessionStart",
            "source": "compact",
        })
        assert result.returncode == 0
        # No output expected — silent exit
        assert result.stdout.strip() == ""
