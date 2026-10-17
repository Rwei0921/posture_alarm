"""Control-panel persistence and validation without GUI, secrets or hardware."""

from __future__ import annotations

import math
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core.control_settings import (
    BALANCED_PRESET, NOTIFICATION_KEYS, SENSITIVE_PRESET, parse_env, read_env,
    update_env, validate_notifications, validate_thresholds,
)


@pytest.mark.parametrize("value", ("nan", "inf", "-inf", "0", "91", "abc"))
def test_angle_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="角度"):
        validate_thresholds({**BALANCED_PRESET, "FALL_TRUNK_ANGLE_THRESHOLD_DEG": value})


def test_presets_validate_and_defaults_match_clean_runtime():
    import importlib
    import config
    with patch.dict("os.environ", {}, clear=True):
        importlib.reload(config)
        for key, value in validate_thresholds(BALANCED_PRESET).items():
            assert math.isclose(float(value), getattr(config, key))
    importlib.reload(config)
    assert validate_thresholds(SENSITIVE_PRESET)["FALL_SCORE_THRESHOLD"] == "0.55"


def test_window_and_time_relationships_are_validated():
    for changed in (
        {"FALL_SCORE_WINDOW_SIZE": "2.5"},
        {"FALL_EVENT_WINDOW_SECONDS": "0.1"},
        {"SUSPECT_FALL_TIMEOUT": "0.1"},
    ):
        with pytest.raises(ValueError):
            validate_thresholds({**BALANCED_PRESET, **changed})


def test_private_atomic_update_preserves_unrelated_settings_and_removes_duplicates(tmp_path):
    path = tmp_path / "demo.env"
    path.write_text("# Keep this comment\nCAMERA_SOURCE=0\nLED_GPIO_PIN=18\nLINE_TARGET_ID=old\nLINE_TARGET_ID=duplicate\n", encoding="utf-8")
    before = read_env(path)
    secret = "dummy value with $() # ' and &"
    update_env(path, {"LINE_TARGET_ID": secret}, expected=before)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Keep this comment\nCAMERA_SOURCE=0\nLED_GPIO_PIN=18\n")
    assert text.count("LINE_TARGET_ID=") == 1
    assert read_env(path)["LINE_TARGET_ID"] == secret
    assert list(tmp_path.iterdir()) == [path]
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_atomic_failure_keeps_original_file(tmp_path):
    path = tmp_path / "demo.env"
    path.write_text("LINE_TARGET_ID=old\n", encoding="utf-8")
    with patch("core.control_settings.os.replace", side_effect=OSError("disk unavailable")):
        with pytest.raises(OSError):
            update_env(path, {"LINE_TARGET_ID": "new"})
    assert path.read_text() == "LINE_TARGET_ID=old\n"
    assert list(tmp_path.iterdir()) == [path]


def test_conflict_rejects_stale_updates_and_unrelated_changes_survive(tmp_path):
    path = tmp_path / "demo.env"
    path.write_text("LINE_TARGET_ID=old\n", encoding="utf-8")
    before = read_env(path)
    path.write_text("LINE_TARGET_ID=other\n", encoding="utf-8")
    with pytest.raises(ValueError, match="其他程式"):
        update_env(path, {"LINE_TARGET_ID": "mine"}, expected=before)
    path.write_text("LINE_TARGET_ID=old\nLED_GPIO_PIN=18\n", encoding="utf-8")
    update_env(path, {"LINE_TARGET_ID": "mine"}, expected=before)
    assert read_env(path)["LED_GPIO_PIN"] == "18"


def test_notification_validation_and_error_messages_do_not_echo_credentials():
    assert all(value == "" for value in validate_notifications({}).values())
    for value in ("https://example.com/api/webhooks/id/dummy-secret", "secret\nsecond-line"):
        with pytest.raises(ValueError) as error:
            validate_notifications({"DISCORD_WEBHOOK_URL": value})
        assert value not in str(error.value)
    assert validate_notifications({"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/dummy-token"})


def test_env_is_data_never_executed_and_errors_hide_values():
    assert parse_env("export LINE_TARGET_ID='$(do-not-run)'\n")["LINE_TARGET_ID"] == "$(do-not-run)"
    with pytest.raises(ValueError) as error:
        parse_env("LINE_CHANNEL_ACCESS_TOKEN='dummy-secret")
    assert "dummy-secret" not in str(error.value)


def test_only_gui_settings_can_be_written(tmp_path):
    for values in ({"BUZZER_GPIO_PIN": "99"}, {"LINE_TARGET_ID": "one\ntwo"}):
        with pytest.raises(ValueError):
            update_env(tmp_path / "demo.env", values)


def test_clearing_notification_writes_explicit_empty_value(tmp_path):
    path = tmp_path / "demo.env"
    path.write_text("DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123/dummy\n", encoding="utf-8")
    update_env(path, {"DISCORD_WEBHOOK_URL": ""})
    assert read_env(path)["DISCORD_WEBHOOK_URL"] == ""
