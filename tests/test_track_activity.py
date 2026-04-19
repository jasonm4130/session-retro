"""Tests for scripts/track-activity.sh — PreToolUse activity tracking hook."""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "track-activity.sh"


def run_hook(
    stdin_data: dict, plugin_data: Path, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    """Run the track-activity.sh hook with the given stdin JSON."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        env=env,
    )


def make_stdin(
    session_id="test-session-001",
    tool_name="Read",
    tool_input=None,
    transcript_path="/tmp/test-session.jsonl",
    cwd="/tmp/test-project",
):
    """Build a hook stdin dict."""
    return {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input or {},
    }


def read_activity(plugin_data: Path, session_id="test-session-001") -> dict:
    """Read and parse the activity JSON file."""
    path = plugin_data / f"activity-{session_id}.json"
    return json.loads(path.read_text())


class TestActivityFileCreation:
    """Test that the activity file is created with correct initial values."""

    def test_creates_activity_file(self, tmp_plugin_data):
        stdin = make_stdin()
        result = run_hook(stdin, tmp_plugin_data)

        assert result.returncode == 0
        activity = read_activity(tmp_plugin_data)
        assert activity["sessionId"] == "test-session-001"
        assert activity["transcriptPath"] == "/tmp/test-session.jsonl"
        assert activity["cwd"] == "/tmp/test-project"
        assert activity["toolCalls"] == 1
        assert activity["filesChanged"] == []
        assert activity["subagentsSpawned"] == 0
        assert activity["gitCommits"] == 0
        assert activity["score"] == 0
        assert "firstSeenAt" in activity
        assert "lastSeenAt" in activity


class TestToolCallCounting:
    """Test that tool calls are counted correctly."""

    def test_increments_tool_calls(self, tmp_plugin_data):
        stdin = make_stdin()
        run_hook(stdin, tmp_plugin_data)
        run_hook(stdin, tmp_plugin_data)
        run_hook(stdin, tmp_plugin_data)

        activity = read_activity(tmp_plugin_data)
        assert activity["toolCalls"] == 3


class TestFileChangeTracking:
    """Test that file changes from Write/Edit tools are tracked."""

    def test_tracks_write_as_file_change(self, tmp_plugin_data):
        stdin = make_stdin(
            tool_name="Write",
            tool_input={"file_path": "/src/auth.ts", "content": "..."},
        )
        run_hook(stdin, tmp_plugin_data)

        activity = read_activity(tmp_plugin_data)
        assert "/src/auth.ts" in activity["filesChanged"]

    def test_tracks_edit_as_file_change(self, tmp_plugin_data):
        stdin = make_stdin(
            tool_name="Edit",
            tool_input={
                "file_path": "/src/utils.ts",
                "old_string": "a",
                "new_string": "b",
            },
        )
        run_hook(stdin, tmp_plugin_data)

        activity = read_activity(tmp_plugin_data)
        assert "/src/utils.ts" in activity["filesChanged"]

    def test_deduplicates_file_changes(self, tmp_plugin_data):
        stdin = make_stdin(
            tool_name="Write",
            tool_input={"file_path": "/src/auth.ts", "content": "v1"},
        )
        run_hook(stdin, tmp_plugin_data)
        run_hook(stdin, tmp_plugin_data)

        activity = read_activity(tmp_plugin_data)
        assert activity["filesChanged"].count("/src/auth.ts") == 1


class TestSubagentTracking:
    """Test that Agent tool calls are tracked."""

    def test_tracks_agent_as_subagent(self, tmp_plugin_data):
        stdin = make_stdin(
            tool_name="Agent",
            tool_input={"prompt": "do something"},
        )
        run_hook(stdin, tmp_plugin_data)

        activity = read_activity(tmp_plugin_data)
        assert activity["subagentsSpawned"] == 1


class TestGitCommitTracking:
    """Test that git commit commands are tracked."""

    def test_tracks_git_commit(self, tmp_plugin_data):
        stdin = make_stdin(
            tool_name="Bash",
            tool_input={"command": 'git commit -m "fix: something"'},
        )
        run_hook(stdin, tmp_plugin_data)

        activity = read_activity(tmp_plugin_data)
        assert activity["gitCommits"] == 1


class TestNudgeBehavior:
    """Test nudge output based on thresholds."""

    def test_no_output_below_threshold(self, tmp_plugin_data):
        """Below minToolCalls, stdout should be empty."""
        stdin = make_stdin()
        result = run_hook(stdin, tmp_plugin_data)

        assert result.stdout.strip() == ""

    def test_emits_nudge_when_threshold_met(self, tmp_plugin_data):
        """Build a session that meets all nudge conditions."""
        session_id = "nudge-test-001"

        # First call to create the activity file
        stdin = make_stdin(session_id=session_id)
        run_hook(stdin, tmp_plugin_data)

        # Backdate firstSeenAt to 15 minutes ago so elapsed time passes
        activity_path = tmp_plugin_data / f"activity-{session_id}.json"
        activity = json.loads(activity_path.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        activity["firstSeenAt"] = past
        activity_path.write_text(json.dumps(activity))

        # Add 3 file changes first (tool calls 2-4, score=6 — below threshold)
        for i in range(3):
            stdin = make_stdin(
                session_id=session_id,
                tool_name="Write",
                tool_input={"file_path": f"/src/file{i}.ts", "content": "..."},
            )
            run_hook(stdin, tmp_plugin_data)

        # 5th call: 4th unique file, pushing score to 8 and toolCalls to 5
        # This call should trigger the nudge
        stdin = make_stdin(
            session_id=session_id,
            tool_name="Write",
            tool_input={"file_path": "/src/file3.ts", "content": "..."},
        )
        result = run_hook(stdin, tmp_plugin_data)

        output = result.stdout.strip()
        assert output != "", "Expected nudge output but got empty string"
        parsed = json.loads(output)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "session-retro:retro" in ctx
        assert "score" in ctx.lower() or "score" in ctx

    def test_nudge_sets_flag_file(self, tmp_plugin_data):
        """After nudge, the flag file should exist."""
        session_id = "flag-test-001"

        # Create and backdate the activity file
        stdin = make_stdin(session_id=session_id)
        run_hook(stdin, tmp_plugin_data)

        activity_path = tmp_plugin_data / f"activity-{session_id}.json"
        activity = json.loads(activity_path.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        activity["firstSeenAt"] = past
        activity_path.write_text(json.dumps(activity))

        # Build score to 8+ with 4 unique files (calls 2-5 bring toolCalls to 5)
        # The 5th call (4th file) crosses both toolCalls and score thresholds
        for i in range(4):
            stdin = make_stdin(
                session_id=session_id,
                tool_name="Write",
                tool_input={"file_path": f"/src/file{i}.ts", "content": "..."},
            )
            run_hook(stdin, tmp_plugin_data)

        flag = tmp_plugin_data / f"nudge-sent-{session_id}.flag"
        assert flag.exists(), "Flag file should exist after nudge"

    def test_no_repeat_nudge(self, tmp_plugin_data):
        """After first nudge, subsequent calls should produce no output."""
        session_id = "repeat-test-001"

        # Create and backdate
        stdin = make_stdin(session_id=session_id)
        run_hook(stdin, tmp_plugin_data)

        activity_path = tmp_plugin_data / f"activity-{session_id}.json"
        activity = json.loads(activity_path.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        activity["firstSeenAt"] = past
        activity_path.write_text(json.dumps(activity))

        # Build score — 3 files first (calls 2-4, not yet at threshold)
        for i in range(3):
            stdin = make_stdin(
                session_id=session_id,
                tool_name="Write",
                tool_input={"file_path": f"/src/file{i}.ts", "content": "..."},
            )
            run_hook(stdin, tmp_plugin_data)

        # 5th call triggers nudge (4th file, score=8, toolCalls=5)
        stdin = make_stdin(
            session_id=session_id,
            tool_name="Write",
            tool_input={"file_path": "/src/file3.ts", "content": "..."},
        )
        first_result = run_hook(stdin, tmp_plugin_data)
        assert first_result.stdout.strip() != ""

        # Subsequent call should be silent (flag file exists)
        stdin = make_stdin(session_id=session_id)
        second_result = run_hook(stdin, tmp_plugin_data)
        assert second_result.stdout.strip() == ""

    def test_disabled_config_skips_nudge(self, tmp_plugin_data):
        """With enabled:false in config.json, no nudge should be emitted."""
        session_id = "disabled-test-001"

        # Write config with enabled=false
        config = {"enabled": False}
        (tmp_plugin_data / "config.json").write_text(json.dumps(config))

        # Create and backdate
        stdin = make_stdin(session_id=session_id)
        run_hook(stdin, tmp_plugin_data)

        activity_path = tmp_plugin_data / f"activity-{session_id}.json"
        activity = json.loads(activity_path.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        activity["firstSeenAt"] = past
        activity_path.write_text(json.dumps(activity))

        # Build score
        for i in range(4):
            stdin = make_stdin(
                session_id=session_id,
                tool_name="Write",
                tool_input={"file_path": f"/src/file{i}.ts", "content": "..."},
            )
            run_hook(stdin, tmp_plugin_data)

        # Should NOT nudge even though thresholds are met
        stdin = make_stdin(session_id=session_id)
        result = run_hook(stdin, tmp_plugin_data)
        assert result.stdout.strip() == ""


class TestRobustness:
    """Test error handling and robustness."""

    def test_exits_zero_always(self, tmp_plugin_data):
        """Hook should always exit 0, even with bad input."""
        result = run_hook({"garbage": True}, tmp_plugin_data)
        assert result.returncode == 0

    def test_handles_missing_plugin_data(self, tmp_path):
        """Should not crash if CLAUDE_PLUGIN_DATA dir doesn't exist — creates it."""
        nonexistent = tmp_path / "does-not-exist"
        stdin = make_stdin()
        result = run_hook(stdin, nonexistent)

        assert result.returncode == 0
        assert nonexistent.exists()
