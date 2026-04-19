"""Tests for configuration loading."""

import json

from lib.config import load_config, DEFAULT_CONFIG


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_plugin_data):
        config = load_config(tmp_plugin_data)
        assert config["sensitivity"] == "normal"
        assert config["minToolCalls"] == 5
        assert config["minDurationMinutes"] == 10
        assert config["enabled"] is True

    def test_loads_from_file(self, tmp_plugin_data):
        config_path = tmp_plugin_data / "config.json"
        config_path.write_text(json.dumps({"sensitivity": "high"}))
        config = load_config(tmp_plugin_data)
        assert config["sensitivity"] == "high"
        assert config["minToolCalls"] == 5

    def test_partial_config_merges_with_defaults(self, tmp_plugin_data):
        config_path = tmp_plugin_data / "config.json"
        config_path.write_text(json.dumps({
            "minToolCalls": 20,
            "signals": {"gitCommitsWeight": 5},
        }))
        config = load_config(tmp_plugin_data)
        assert config["minToolCalls"] == 20
        assert config["signals"]["gitCommitsWeight"] == 5
        assert config["signals"]["fileChangesWeight"] == 2

    def test_disabled_config(self, tmp_plugin_data):
        config_path = tmp_plugin_data / "config.json"
        config_path.write_text(json.dumps({"enabled": False}))
        config = load_config(tmp_plugin_data)
        assert config["enabled"] is False

    def test_malformed_config_returns_defaults(self, tmp_plugin_data):
        config_path = tmp_plugin_data / "config.json"
        config_path.write_text("not json{{{")
        config = load_config(tmp_plugin_data)
        assert config == DEFAULT_CONFIG

    def test_get_threshold_for_sensitivity(self, tmp_plugin_data):
        config = load_config(tmp_plugin_data)
        assert config["thresholds"]["normal"] == 8
        assert config["thresholds"]["low"] == 15
        assert config["thresholds"]["high"] == 3

    def test_project_overrides(self, tmp_plugin_data):
        config_path = tmp_plugin_data / "config.json"
        config_path.write_text(json.dumps({
            "projectOverrides": {
                "**/scratch/**": {"enabled": False},
            }
        }))
        config = load_config(tmp_plugin_data)
        assert "**/scratch/**" in config["projectOverrides"]
