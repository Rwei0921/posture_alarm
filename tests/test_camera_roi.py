"""Camera/ROI control regressions without real cameras, Tk windows or GPIO."""

from __future__ import annotations

from contextlib import ExitStack
import io
import json
from pathlib import Path
from queue import Queue
from threading import Event
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import config
import main as app
from control_worker import camera_preview, worker
from core.control_process import MonitorProcess
from core.control_settings import read_env, update_env
from core.preview_stream import PreviewStream
from core.roi import apply_roi, image_point, roi_from_settings, roi_to_env, validate_points
from tests.test_runtime_regressions import _runtime_mocks
from ui.camera_roi import CameraROI
from ui.control_panel import ControlPanel


POINTS = [(0.1, 0.2), (0.9, 0.2), (0.85, 0.8), (0.15, 0.8)]


@pytest.mark.parametrize("points", [[], POINTS[:3], [(0, 0)] * 4,
    [(0, 0), (1, 1), (1, 0), (0, 1)], [(0, 0), (1, 0), (0.2, 0.2), (0, 1)],
    [(0, 0), (1, 0), (1, float("nan")), (0, 1)],
    [(0, 0), (1, 0), (1, float("inf")), (0, 1)],
    [(-0.1, 0), (1, 0), (1, 1), (0, 1)],
    [(0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01)]])
def test_invalid_roi_rejected_without_partial_config_change(points):
    settings = SimpleNamespace(BED_ROI_ENABLED=False)
    with pytest.raises(ValueError):
        apply_roi(settings, points)
    assert vars(settings) == {"BED_ROI_ENABLED": False}


def test_roundtrip_polygon_and_legacy_rectangle():
    settings = SimpleNamespace()
    apply_roi(settings, POINTS)
    assert roi_from_settings({}, settings) == POINTS
    assert settings.BED_ROI_X1 == 0.1
    assert settings.BED_ROI_Y2 == 0.8
    settings.BED_POLYGON_ENABLED = False
    assert roi_from_settings({}, settings) == [(0.1, 0.2), (0.9, 0.2), (0.9, 0.8), (0.1, 0.8)]
    settings.BED_ROI_ENABLED = False
    assert roi_from_settings({}, settings) == []


def test_polygon_preview_matches_existing_runtime_precedence():
    settings = SimpleNamespace()
    apply_roi(settings, POINTS)
    settings.BED_ROI_ENABLED = False
    assert roi_from_settings({}, settings) == POINTS


def test_click_coordinates_ignore_black_bars_and_survive_resizing():
    assert image_point(20, 50, (100, 20, 400, 300)) is None
    assert image_point(200, 95, (100, 20, 400, 300)) == (0.25, 0.25)
    assert image_point(200, 250, (0, 100, 800, 600)) == (0.25, 0.25)
    assert image_point(0, 0, (0, 0, 0, 0)) is None


def test_roi_persistence_keeps_gpio_credentials_and_rejects_concurrent_edits(tmp_path):
    path = tmp_path / "demo.env"
    original = "LED_GPIO_PIN=18\nLINE_CHANNEL_ACCESS_TOKEN=dummy-secret\n# keep comment\n"
    path.write_text(original, encoding="utf-8")
    expected = read_env(path)
    update_env(path, roi_to_env(POINTS), expected)
    assert path.read_text().startswith(original)
    assert roi_from_settings(read_env(path), SimpleNamespace()) == POINTS
    with pytest.raises(ValueError, match="其他程式"):
        update_env(path, roi_to_env(POINTS), expected)
    with pytest.raises(ValueError):
        update_env(path, {"BUZZER_GPIO_PIN": "22"})


def test_only_latest_frame_is_kept_separately_from_status():
    controller = MonitorProcess(Path("."), Path("unused.env"))
    for index in range(20):
        controller._post({"type": "frame", "png": str(index)})
    controller._post({"type": "status", "data": {"phase": "running"}})
    assert controller.frames.qsize() == 1
    assert controller.take_frame()["png"] == "19"
    assert controller.take_frame() is None
    assert len(controller.drain()) == 1


def test_gui_worker_exclusively_embeds_preview_and_supports_json_commands(tmp_path):
    controller = MonitorProcess(tmp_path, tmp_path / "demo.env")
    with patch("core.control_process.subprocess.Popen") as popen, patch("core.control_process.threading.Thread"):
        controller.start("camera")
        environment = popen.call_args.kwargs["env"]
        assert environment["SHOW_WINDOW"] == environment["BED_ROI_MARK_ON_START"] == "0"
        assert controller.send_command({"command": "roi", "points": POINTS})
        command = json.loads(popen.return_value.stdin.write.call_args.args[0])
        assert command["command"] == "roi"
        controller.stop()
        assert not controller.send_command({"command": "preview", "enabled": True})


def test_preview_hidden_does_not_copy_or_encode_frames_and_roi_waits_for_boundary():
    settings = SimpleNamespace(GUI_PREVIEW_FPS=5, BED_ROI_ENABLED=False)
    send = Mock()
    stream = PreviewStream(settings, send)
    try:
        frame = Mock()
        stream.offer(frame)
        frame.copy.assert_not_called()
        stream.command({"command": "roi", "points": POINTS})
        assert settings.BED_ROI_ENABLED is False
        stream.apply_pending()
        assert settings.BED_ROI_ENABLED is True
        send.assert_called_once_with({"type": "roi_applied", "points": POINTS})
        stream.apply_pending()
        send.assert_called_once()
    finally:
        stream.close()


def test_png_preview_encoder_preserves_aspect_ratio_without_optional_image_packages():
    # 替身只驗證資料流；不要求測試主機安裝 cv2 或 numpy。
    settings = SimpleNamespace(GUI_PREVIEW_FPS=5, BED_ROI_ENABLED=False)
    frame = Mock(shape=(480, 640, 3))
    frame.copy.return_value = frame
    cv2 = Mock(IMWRITE_PNG_COMPRESSION=16)
    cv2.imencode.return_value = (True, b"dummy-png")
    output = Queue()
    with patch.dict("sys.modules", {"cv2": cv2}):
        stream = PreviewStream(settings, output.put)
        try:
            stream.command({"command": "preview", "enabled": True, "width": 320, "height": 300})
            stream.offer(frame)
            message = output.get(timeout=2)
            assert message["type"] == "frame"
            assert message["png"] == "ZHVtbXktcG5n"
            cv2.resize.assert_called_once_with(frame, (320, 240))
        finally:
            stream.close()


def test_camera_only_preview_releases_camera_and_never_loads_monitoring_pipeline():
    stop = Event()
    stream, emit = Mock(), Mock()
    def read():
        stop.set()
        return True, Mock()
    with patch("vision.camera.Camera") as camera, patch("main.run") as run:
        camera.return_value.read_frame.side_effect = read
        camera_preview(stop, stream, emit)
        camera.return_value.release.assert_called_once()
        stream.offer.assert_called_once()
        run.assert_not_called()
        assert emit.call_args.args[0]["phase"] == "stopped"


def test_failed_preview_camera_is_bounded_and_released():
    with patch("vision.camera.Camera") as camera, patch.object(config, "CAMERA_MAX_READ_FAILURES", 1):
        camera.return_value.read_frame.return_value = (False, None)
        with pytest.raises(RuntimeError):
            camera_preview(Event(), Mock(), Mock())
        camera.return_value.read_frame.assert_called_once()
        camera.return_value.release.assert_called_once()


def test_runtime_handles_roi_command_before_frame_and_reuses_same_frame_for_preview():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        stack.enter_context(patch.object(app, "EventDB"))
        mocks["Camera"].read_frame.side_effect = [(True, Mock()), (False, None)]
        mocks["PoseEstimator"].extract_landmarks.return_value = []
        preview, boundary = Mock(), Mock()
        order = Mock()
        order.attach_mock(boundary, "boundary")
        order.attach_mock(mocks["Camera"].read_frame, "read")
        app.run(frame_callback=preview, control_callback=boundary)
        assert order.mock_calls[0].call_list()[0][0] == "boundary"
        preview.assert_called_once()
        mocks["Camera"].release.assert_called_once()


def panel_stub(tmp_path):
    panel = object.__new__(ControlPanel)
    panel.preview = panel.closing = panel.restart_pending = panel.roi_start_pending = panel.monitor_after_roi = False
    panel.controller = Mock(busy=True, mode="camera", stopping=False)
    panel.camera_view = Mock(editing=False)
    panel.camera_view.selection.return_value = POINTS
    panel.env_path = tmp_path / "demo.env"
    panel.disk_values = {}
    panel.defaults = SimpleNamespace(GUI_ROI_ON_START=True)
    panel.notebook, panel.camera_tab, panel.dialog, panel.root = Mock(), Mock(), Mock(), Mock()
    panel.feedback, panel._record, panel._launch_monitor = Mock(), Mock(), Mock()
    return panel


def test_start_routes_to_roi_setup_without_starting_detection(tmp_path):
    panel = panel_stub(tmp_path)
    panel._form = Mock(return_value={})
    panel.saved_form = {}
    panel._open_camera = Mock()
    panel._start()
    assert panel.roi_start_pending
    panel._open_camera.assert_called_once()
    panel._launch_monitor.assert_not_called()


def test_confirm_roi_waits_for_camera_preview_exit_before_monitor_start(tmp_path):
    panel = panel_stub(tmp_path)
    panel._confirm_roi(True)
    assert panel.monitor_after_roi
    panel.controller.stop.assert_called_once()
    panel._launch_monitor.assert_not_called()
    assert roi_from_settings(read_env(panel.env_path), SimpleNamespace()) == POINTS


def test_save_roi_during_monitoring_does_not_restart_or_stop_detection(tmp_path):
    panel = panel_stub(tmp_path)
    panel.controller.mode = "monitor"
    panel._confirm_roi(False)
    panel.controller.send_command.assert_called_once_with({"command": "roi", "points": POINTS})
    panel.controller.stop.assert_not_called()
    panel._launch_monitor.assert_not_called()


def test_hide_monitor_preview_does_not_stop_monitoring(tmp_path):
    panel = panel_stub(tmp_path)
    panel.controller.mode = "monitor"
    panel.notebook.select.return_value = "status-tab"
    panel._tab_changed()
    panel.controller.stop.assert_not_called()
    assert panel.controller.send_command.call_args.args[0]["enabled"] is False


def test_manual_stop_cancels_pending_monitor_start(tmp_path):
    panel = panel_stub(tmp_path)
    panel.monitor_after_roi = True
    panel._stop()
    assert panel.monitor_after_roi is False
    panel.controller.stop.assert_called_once()


def test_stale_canvas_image_cannot_be_confirmed():
    view = object.__new__(CameraROI)
    view.photo = Mock()
    view.last_frame = time.monotonic() - 4
    view.editing, view.points = False, POINTS
    with pytest.raises(ValueError, match="尚未更新"):
        view.selection()


def prepare_refresh(panel, messages):
    panel.controller.drain.return_value = messages
    panel.controller.take_frame.return_value = None
    panel.controller.busy = False
    panel.camera_view.photo = None
    panel.preview_visible = False
    panel.results = Queue()
    panel.test_buttons = []
    panel.last_received = 0
    panel.defaults.GUI_REFRESH_MS = 500
    panel._apply_snapshot = Mock()
    for name in ("start_button", "stop_button", "alarm_button", "save_button", "restart_button", "reload_button"):
        setattr(panel, name, Mock())


def test_monitor_launch_occurs_only_after_successful_preview_exit(tmp_path):
    panel = panel_stub(tmp_path)
    panel._confirm_roi(True)
    prepare_refresh(panel, [{"type": "exit", "code": 0}])
    panel._refresh()
    panel._launch_monitor.assert_called_once()
    assert panel.monitor_after_roi is False


@pytest.mark.parametrize("cancel", ["stop", "error"])
def test_preview_stop_or_error_cannot_trigger_delayed_monitor_start(tmp_path, cancel):
    panel = panel_stub(tmp_path)
    panel.monitor_after_roi = True
    messages = [{"type": "exit", "code": 0}]
    if cancel == "stop":
        panel._stop()
    else:
        messages = [{"type": "error", "error_type": "RuntimeError"}, {"type": "exit", "code": 1}]
    prepare_refresh(panel, messages)
    panel._refresh()
    panel._launch_monitor.assert_not_called()


def test_worker_accepts_camera_commands_and_stop_without_leaking_raw_input():
    commands = [json.dumps({"command": "preview", "enabled": True}),
                json.dumps({"command": "roi", "points": POINTS}), "dummy-secret", "stop"]
    output = io.StringIO()
    with patch("control_worker.PreviewStream") as stream, patch("control_worker.Thread") as reader, \
            patch("sys.stdin", io.StringIO("\n".join(commands))), patch("sys.stdout", output), \
            patch("vision.camera.Camera._load_cv2"), patch("main.run") as run:
        reader.return_value.start.side_effect = lambda: reader.call_args.kwargs["target"]()
        assert worker("monitor") == 0
        assert stream.return_value.command.call_count == 2
        assert run.call_args.kwargs["stop_event"].is_set()
        assert run.call_args.kwargs["control_callback"] == stream.return_value.apply_pending
        stream.return_value.close.assert_called_once()
    assert "dummy-secret" not in output.getvalue()
    assert "command_error" in output.getvalue()


def test_native_camera_import_completes_before_stdin_reader_starts():
    order = Mock()
    with patch("vision.camera.Camera._load_cv2") as load, patch("control_worker.Thread") as reader, \
            patch("control_worker.PreviewStream"), patch("main.run"), patch("sys.stdout", io.StringIO()):
        order.attach_mock(load, "load_native")
        order.attach_mock(reader.return_value.start, "start_reader")
        assert worker("monitor") == 0
    assert [call[0] for call in order.mock_calls] == ["load_native", "start_reader"]
