"""Control orchestration checks that never require a window or real services."""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import config
from core.control_process import MESSAGE_PREFIX, MonitorProcess, test_notification as send_notification
from core.control_settings import BALANCED_PRESET, NOTIFICATION_KEYS, SECRET_MASK
from core.monitor_status import explain_status
from ui.control_panel import ControlPanel


def test_gui_import_does_not_import_tk_or_open_hardware():
    with patch.dict(sys.modules, {"tkinter": None, "cv2": None, "mediapipe": None}):
        importlib.reload(importlib.import_module("ui.control_panel"))


def test_process_uses_current_interpreter_and_settings_without_command_line_secrets(tmp_path):
    path = tmp_path / "demo.env"
    path.write_text("LED_GPIO_PIN=18\nLINE_CHANNEL_ACCESS_TOKEN=dummy-secret\n", encoding="utf-8")
    controller = MonitorProcess(tmp_path, path)
    with patch("core.control_process.subprocess.Popen") as popen, patch("core.control_process.threading.Thread"):
        controller.start()
        args, kwargs = popen.call_args
        assert args[0][0] == sys.executable
        assert "dummy-secret" not in str(args)
        assert kwargs["env"]["LINE_CHANNEL_ACCESS_TOKEN"] == "dummy-secret"
        assert kwargs["env"]["LED_GPIO_PIN"] == "18"
        assert kwargs["env"]["GUI_ENABLED"] == "0"
        try:
            controller.start()
        except RuntimeError:
            pass
        else:
            raise AssertionError("Duplicate worker allowed")
        controller.stop()
        popen.return_value.stdin.write.assert_called_once_with("stop\n")


def test_output_reader_discards_raw_logs_and_exit_releases_controller(tmp_path):
    controller = MonitorProcess(tmp_path, tmp_path / "demo.env")
    process = Mock()
    process.stdout = io.StringIO("raw error contains dummy-secret\n" + MESSAGE_PREFIX + json.dumps({"type": "status", "data": {"state": "NORMAL"}}) + "\n")
    process.wait.return_value = 0
    controller.process = process
    controller._read_output(process)
    messages = controller.drain()
    assert "dummy-secret" not in str(messages)
    assert messages[0]["data"]["state"] == "NORMAL"
    assert messages[-1] == {"type": "exit", "code": 0}
    assert not controller.busy
    process.stdin.close.assert_called_once()


def test_notification_uses_existing_notifiers_only():
    values = dict(zip(NOTIFICATION_KEYS, ("dummy-token", "dummy-user", "https://discord.com/api/webhooks/123/dummy")))
    with patch("alert.notifier_line.LineNotifier") as line, patch("alert.notifier_discord.DiscordNotifier") as discord:
        line.return_value.send.return_value = True
        assert send_notification("line", values) is True
        line.assert_called_once_with("dummy-token", "dummy-user")
        line.return_value.send.assert_called_once_with("Posture Alarm GUI test notification")
        send_notification("discord", values)
        discord.assert_called_once_with(values["DISCORD_WEBHOOK_URL"])


def test_no_display_retains_cli_and_disables_opencv_windows(tmp_path):
    import run_gui
    with patch.object(run_gui, "read_env", return_value={}), patch.dict(sys.modules, {"tkinter": None}), patch("main.run") as run:
        run_gui.launch()
        run.assert_called_once_with()
        assert not config.SHOW_WINDOW
        assert not config.BED_ROI_MARK_ON_START
    importlib.reload(config)


def test_panel_has_masked_notification_fields_without_building_a_window():
    panel = object.__new__(ControlPanel)
    panel.ttk = Mock()
    panel.tk = Mock()
    panel.fields, panel.entries, panel.test_buttons = {}, {}, []
    panel.colors = {"muted": "grey"}
    panel._build_notifications(Mock())
    assert SECRET_MASK == "*"
    assert [call.kwargs["show"] for call in panel.ttk.Entry.call_args_list] == ["*"] * 3


def test_restart_waits_for_current_process_exit_before_starting():
    panel = object.__new__(ControlPanel)
    panel.controller = Mock(busy=True, mode="monitor")
    panel.feedback = Mock()
    panel._save = Mock(return_value=True)
    panel._start = Mock()
    panel._restart()
    assert panel.restart_pending is True
    panel.controller.stop.assert_called_once()
    panel._start.assert_not_called()


def test_save_updates_changed_values_only_and_never_gpio(tmp_path):
    path = tmp_path / "demo.env"
    path.write_text("LED_GPIO_PIN=18\nFALL_SCORE_THRESHOLD=0.7\n", encoding="utf-8")
    panel = object.__new__(ControlPanel)
    panel.preview = False
    panel.env_path = path
    panel.disk_values = {"LED_GPIO_PIN": "18", "FALL_SCORE_THRESHOLD": "0.7"}
    panel.saved_form = {**BALANCED_PRESET, **dict.fromkeys(NOTIFICATION_KEYS, "")}
    panel.saved_form["FALL_SCORE_THRESHOLD"] = "0.7"
    panel.fields = {key: Mock() for key in panel.saved_form}
    panel._form = Mock(return_value={**panel.saved_form, "FALL_SCORE_THRESHOLD": "0.55"})
    panel.feedback = Mock()
    assert panel._save() is True
    text = path.read_text()
    assert "LED_GPIO_PIN=18" in text
    assert "FALL_SCORE_THRESHOLD=0.55" in text
    assert "LINE_CHANNEL_ACCESS_TOKEN" not in text


def test_reasons_distinguish_event_gate_person_gate_bed_and_confirmation():
    base = {"phase": "running", "camera_ok": True, "person_present": True}
    assert "人體" in explain_status({**base, "person_present": False})
    assert "沒有保留中的跌倒事件" in explain_status(base)
    assert "床區" in explain_status({**base, "safe_lying_detected": True})
    assert "等待確認" in explain_status({**base, "state": "SUSPECT_FALL", "fall_detected": True})
    assert "模擬" in explain_status({**base, "state": "FALLEN", "gpio_simulated": True})


def test_real_child_can_stop_cleanly_without_gpio_or_camera(tmp_path):
    path = tmp_path / "demo.env"
    path.write_text("SIMULATE_GPIO=1\n", encoding="utf-8")
    project = Path(__file__).resolve().parents[1]
    controller = MonitorProcess(project, path)
    controller.start("alarm_test")
    controller.stop()
    assert controller.process.wait(timeout=10) == 0
    controller._reader.join(timeout=5)
    messages = controller.drain()
    assert messages[-1] == {"type": "exit", "code": 0}
    assert not controller.busy
    assert not any(message.get("type") == "error" for message in messages)


def test_worker_error_reports_type_without_secret_text():
    import control_worker
    stream = io.StringIO()
    with patch("main.run", side_effect=RuntimeError("dummy-secret")), patch("vision.camera.Camera._load_cv2"), patch("sys.stdin", io.StringIO("stop\n")), patch("sys.stdout", stream):
        assert control_worker.worker("monitor") == 1
    assert "dummy-secret" not in stream.getvalue()
    assert "RuntimeError" in stream.getvalue()
