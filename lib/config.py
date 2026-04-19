"""Configuration loading with defaults and project overrides."""

import json
from pathlib import Path

DEFAULT_CONFIG = {
    "sensitivity": "normal",
    "minToolCalls": 5,
    "minDurationMinutes": 10,
    "signals": {
        "fileChangesWeight": 2,
        "subagentSpawnsWeight": 2,
        "gitCommitsWeight": 1,
    },
    "thresholds": {
        "low": 15,
        "normal": 8,
        "high": 3,
    },
    "projectOverrides": {},
    "enabled": True,
}


def load_config(plugin_data_dir: str | Path) -> dict:
    """Load config from plugin data dir, merging with defaults."""
    config_path = Path(plugin_data_dir) / "config.json"

    if not config_path.exists():
        return dict(DEFAULT_CONFIG)

    try:
        user_config = json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)

    return _deep_merge(DEFAULT_CONFIG, user_config)


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Recursively merge overrides into defaults."""
    result = {}
    for key, default_val in defaults.items():
        if key in overrides:
            override_val = overrides[key]
            if isinstance(default_val, dict) and isinstance(override_val, dict):
                result[key] = _deep_merge(default_val, override_val)
            else:
                result[key] = override_val
        else:
            result[key] = default_val

    for key in overrides:
        if key not in defaults:
            result[key] = overrides[key]

    return result
