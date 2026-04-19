"""Shared fixtures for session-retro tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_plugin_data(tmp_path):
    """Temporary directory simulating $CLAUDE_PLUGIN_DATA."""
    data_dir = tmp_path / "plugin-data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def tmp_memory_dir(tmp_path):
    """Temporary directory simulating ~/.claude/projects/{project}/memory/."""
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    return mem_dir


@pytest.fixture
def sample_hook_stdin():
    """Factory for creating hook stdin JSON."""
    def _make(
        session_id="test-session-001",
        transcript_path="/tmp/test-session.jsonl",
        cwd="/tmp/test-project",
        hook_event_name="PreToolUse",
        tool_name="Read",
        tool_input=None,
        **extra,
    ):
        data = {
            "session_id": session_id,
            "transcript_path": transcript_path,
            "cwd": cwd,
            "hook_event_name": hook_event_name,
            "tool_name": tool_name,
            "tool_input": tool_input or {},
            **extra,
        }
        return json.dumps(data)
    return _make
