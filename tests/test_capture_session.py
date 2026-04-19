"""Tests for capture-session.sh SessionEnd hook."""

import json
import os
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "capture-session.sh"


def run_hook(
    stdin_data: dict,
    plugin_data: Path,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd or str(plugin_data),
    )


def make_stdin(session_id: str = "test-001", source: str = "prompt_input_exit") -> dict:
    return {
        "session_id": session_id,
        "transcript_path": "/tmp/test.jsonl",
        "cwd": "/tmp/test-project",
        "hook_event_name": "SessionEnd",
        "source": source,
    }


def make_activity(
    tool_calls: int = 47,
    files_changed: int = 8,
    subagents_spawned: int = 2,
    git_commits: int = 1,
    score: int = 13,
    started_at: str = "2026-04-19T08:00:00Z",
) -> dict:
    return {
        "toolCalls": tool_calls,
        "filesChanged": files_changed,
        "subagentsSpawned": subagents_spawned,
        "gitCommits": git_commits,
        "score": score,
        "startedAt": started_at,
    }


# ── tests ─────────────────────────────────────────────────────────────────────


def test_creates_pending_retro_when_substantial(tmp_plugin_data):
    """Writes pending-retro JSON when activity score > 0."""
    session_id = "test-001"
    activity = make_activity(score=13)

    activity_file = tmp_plugin_data / f"activity-{session_id}.json"
    activity_file.write_text(json.dumps(activity))

    result = run_hook(make_stdin(session_id=session_id), tmp_plugin_data)
    assert result.returncode == 0, result.stderr

    pending_file = tmp_plugin_data / f"pending-retro-{session_id}.json"
    assert pending_file.exists(), "pending-retro file should be created"

    data = json.loads(pending_file.read_text())

    # Required schema keys
    assert data["sessionId"] == session_id
    assert data["transcriptPath"] == "/tmp/test.jsonl"
    assert data["cwd"] == "/tmp/test-project"
    assert data["exitReason"] == "prompt_input_exit"
    assert "startedAt" in data
    assert "endedAt" in data
    assert "activity" in data
    assert "gitDiffStat" in data

    # Activity fields preserved
    activity_out = data["activity"]
    assert activity_out["score"] == 13
    assert activity_out["toolCalls"] == 47
    assert activity_out["filesChanged"] == 8


def test_skips_when_retro_already_done(tmp_plugin_data):
    """Does not write pending-retro if retro-done flag exists."""
    session_id = "test-002"

    # Create activity file (score > 0) and retro-done flag
    activity_file = tmp_plugin_data / f"activity-{session_id}.json"
    activity_file.write_text(json.dumps(make_activity(score=5)))

    retro_done_flag = tmp_plugin_data / f"retro-done-{session_id}.flag"
    retro_done_flag.touch()

    result = run_hook(make_stdin(session_id=session_id), tmp_plugin_data)
    assert result.returncode == 0, result.stderr

    pending_file = tmp_plugin_data / f"pending-retro-{session_id}.json"
    assert not pending_file.exists(), "pending-retro should NOT be created when retro-done flag exists"


def test_cleans_up_session_files(tmp_plugin_data):
    """Deletes activity and nudge-sent files after hook runs."""
    session_id = "test-003"

    activity_file = tmp_plugin_data / f"activity-{session_id}.json"
    nudge_flag = tmp_plugin_data / f"nudge-sent-{session_id}.flag"

    activity_file.write_text(json.dumps(make_activity(score=5)))
    nudge_flag.touch()

    result = run_hook(make_stdin(session_id=session_id), tmp_plugin_data)
    assert result.returncode == 0, result.stderr

    assert not activity_file.exists(), "activity file should be deleted"
    assert not nudge_flag.exists(), "nudge-sent flag should be deleted"


def test_skips_trivial_sessions(tmp_plugin_data):
    """Does not write pending-retro when score == 0."""
    session_id = "test-004"

    activity_file = tmp_plugin_data / f"activity-{session_id}.json"
    activity_file.write_text(json.dumps(make_activity(score=0)))

    result = run_hook(make_stdin(session_id=session_id), tmp_plugin_data)
    assert result.returncode == 0, result.stderr

    pending_file = tmp_plugin_data / f"pending-retro-{session_id}.json"
    assert not pending_file.exists(), "pending-retro should NOT be created for trivial (score=0) sessions"


def test_prunes_stale_flags(tmp_plugin_data):
    """Deletes retro-done and pending-retro files older than 30 days; keeps recent ones."""
    # Stale files (backdate to 31 days ago)
    stale_time = time.time() - (31 * 24 * 3600)

    stale_retro_done = tmp_plugin_data / "retro-done-old-session.flag"
    stale_pending = tmp_plugin_data / "pending-retro-old-session.json"
    stale_retro_done.touch()
    stale_pending.write_text(json.dumps({"sessionId": "old-session"}))
    os.utime(stale_retro_done, (stale_time, stale_time))
    os.utime(stale_pending, (stale_time, stale_time))

    # Recent files (should survive)
    recent_retro_done = tmp_plugin_data / "retro-done-new-session.flag"
    recent_pending = tmp_plugin_data / "pending-retro-new-session.json"
    recent_retro_done.touch()
    recent_pending.write_text(json.dumps({"sessionId": "new-session"}))

    # Run with a trivial session so no other side-effects
    session_id = "test-005"
    result = run_hook(make_stdin(session_id=session_id), tmp_plugin_data)
    assert result.returncode == 0, result.stderr

    # Stale files should be gone
    assert not stale_retro_done.exists(), "stale retro-done flag should be pruned"
    assert not stale_pending.exists(), "stale pending-retro should be pruned"

    # Recent files should survive
    assert recent_retro_done.exists(), "recent retro-done flag should be kept"
    assert recent_pending.exists(), "recent pending-retro should be kept"


def test_handles_no_activity_file(tmp_plugin_data):
    """Does not crash when activity file is missing."""
    session_id = "test-006"

    # No activity file created — should exit cleanly without pending-retro
    result = run_hook(make_stdin(session_id=session_id), tmp_plugin_data)
    assert result.returncode == 0, result.stderr

    pending_file = tmp_plugin_data / f"pending-retro-{session_id}.json"
    assert not pending_file.exists(), "no pending-retro should be written when activity file is absent"
