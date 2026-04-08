import importlib
import re

import config
import core.utils as utils


def test_now_timestamp_uses_app_timezone(monkeypatch):
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Taipei")
    importlib.reload(config)
    reloaded_utils = importlib.reload(utils)

    try:
        timestamp = reloaded_utils.now_timestamp()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00", timestamp)
    finally:
        importlib.reload(config)
        importlib.reload(utils)


def test_build_fall_alert_message_includes_timestamp():
    message = utils.build_fall_alert_message("2026年04月09日 02:14:32")

    assert message == "姿勢警報：偵測到跌倒，時間：2026年04月09日 02:14:32"


def test_display_timestamp_from_iso_uses_same_local_wall_clock():
    display = utils.display_timestamp_from_iso("2026-04-09T02:14:32+08:00")

    assert display == "2026年04月09日 02:14:32"
