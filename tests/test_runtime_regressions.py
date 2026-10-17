"""Hardware-free regression coverage for runtime shutdown and retry limits."""

from __future__ import annotations

import importlib
from contextlib import ExitStack
from unittest.mock import Mock, patch

import config
import main as app
from core.state_machine import PostureState
from storage.db_sqlite import EventDB


def test_event_window_respects_confirmation_and_preserves_longer_values():
    try:
        for requested, expected in (("0.1", 2.0), ("3.0", 3.0)):
            with patch.dict("os.environ", FALL_EVENT_WINDOW_SECONDS=requested, FALL_CONFIRM_SECONDS="2.0"):
                importlib.reload(config)
                assert config.FALL_EVENT_WINDOW_SECONDS == expected
    finally:
        importlib.reload(config)


def test_roi_marker_aborts_after_consecutive_camera_failures():
    cam, cv2, logger = Mock(), Mock(), Mock()
    cam.read_frame.return_value = (False, None)
    with patch.object(config, "CAMERA_MAX_READ_FAILURES", 3), patch.object(app.time, "sleep"):
        assert app._interactive_mark_bed_roi(cam, cv2, 1.0, logger) is False
    assert cam.read_frame.call_count == 3
    cv2.destroyWindow.assert_not_called()


def test_roi_marker_stops_on_shutdown_during_camera_read():
    cam, cv2, logger = Mock(), Mock(), Mock()
    stopped = False

    def read_frame():
        nonlocal stopped
        stopped = True
        return False, None

    cam.read_frame.side_effect = read_frame
    assert app._interactive_mark_bed_roi(cam, cv2, 1.0, logger, lambda: stopped) is False
    cam.read_frame.assert_called_once()
    cv2.destroyWindow.assert_not_called()


def test_roi_marker_shutdown_closes_existing_window():
    cam, cv2, logger = Mock(), Mock(), Mock()
    frame = Mock(shape=(480, 640, 3))
    frame.copy.return_value = frame
    cam.read_frame.side_effect = [(False, None), (True, frame), (False, None)]
    cv2.waitKey.return_value = -1
    with patch.object(config, "CAMERA_MAX_READ_FAILURES", 2), patch.object(app.time, "sleep"):
        assert app._interactive_mark_bed_roi(
            cam, cv2, 1.0, logger, lambda: cam.read_frame.call_count == 3,
        ) is False
    cv2.destroyWindow.assert_called_once_with("Mark BED ROI")


def _runtime_mocks(stack: ExitStack) -> dict[str, Mock]:
    instances = {}
    for name in (
        "Camera", "PersonDetector", "PoseEstimator", "FallClassifier",
        "PostureStateMachine", "BuzzerLED", "LineNotifier", "DiscordNotifier",
        "Reporter", "Overlay",
    ):
        instances[name] = stack.enter_context(patch.object(app, name)).return_value
    stack.enter_context(patch.object(app, "setup_logger", return_value=Mock()))
    stack.enter_context(patch.object(app.signal, "signal"))
    stack.enter_context(patch.object(app.time, "sleep"))
    for name, value in {
        "SHOW_WINDOW": False, "BED_ROI_MARK_ON_START": False,
        "DHT22_ENABLED": False, "CAMERA_MAX_READ_FAILURES": 1,
        "ALERT_COOLDOWN_SECONDS": 60.0,
    }.items():
        stack.enter_context(patch.object(config, name, value))
    return instances


def test_failed_notifications_and_db_writes_are_limited_in_runtime_loop():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        db = EventDB(":memory:")
        stack.callback(db.close)
        stack.enter_context(patch.object(app, "EventDB", return_value=db))
        clock = [0.0]
        timestamps = iter([0.0, 0.01, 59.99, 60.0, 60.01, 120.0])

        def read_frame():
            stamp = next(timestamps, None)
            if stamp is None:
                return False, None
            clock[0] = stamp
            return True, Mock()

        mocks["Camera"].read_frame.side_effect = read_frame
        mocks["PoseEstimator"].extract_landmarks.return_value = []
        mocks["PostureStateMachine"].state = PostureState.FALLEN
        mocks["PostureStateMachine"].update.return_value = PostureState.FALLEN
        mocks["LineNotifier"].send.return_value = False
        mocks["DiscordNotifier"].send.return_value = False
        stack.enter_context(patch.object(app.time, "monotonic", side_effect=lambda: clock[0]))
        # Inspect rows before runtime cleanup closes the in-memory DB.
        rows = []
        real_close = db.close
        stack.enter_context(patch.object(db, "close", side_effect=lambda: rows.extend(db.fetch_recent(10))))
        app.run()
        real_close()
        assert mocks["LineNotifier"].send.call_count == 3
        assert mocks["DiscordNotifier"].send.call_count == 3
        assert len(rows) == 3
        assert all(row["event_type"] == "fall" for row in rows)
        mocks["BuzzerLED"].alert_on.assert_called()


def test_startup_roi_abort_runs_resource_cleanup():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        db = stack.enter_context(patch.object(app, "EventDB")).return_value
        cv2 = stack.enter_context(patch.object(app, "_load_cv2")).return_value
        stack.enter_context(patch.object(config, "BED_ROI_MARK_ON_START", True))
        marker = stack.enter_context(patch.object(app, "_interactive_mark_bed_roi", return_value=False))
        app.run()
        assert callable(marker.call_args.args[-1])
        mocks["Camera"].read_frame.assert_not_called()
        mocks["Camera"].release.assert_called_once()
        for name in ("PoseEstimator", "PersonDetector", "BuzzerLED"):
            mocks[name].close.assert_called_once()
        db.close.assert_called_once()
        cv2.destroyAllWindows.assert_called_once()


def test_roi_marker_success_resets_consecutive_failure_count_and_skip_still_works():
    cam, cv2, logger = Mock(), Mock(), Mock()
    frame = Mock(shape=(480, 640, 3))
    frame.copy.return_value = frame
    cam.read_frame.side_effect = [
        (False, None), (True, frame), (False, None), (True, frame),
    ]
    cv2.waitKey.side_effect = [-1, ord("q")]
    with patch.object(config, "CAMERA_MAX_READ_FAILURES", 2), patch.object(app.time, "sleep"):
        assert app._interactive_mark_bed_roi(cam, cv2, 1.0, logger) is True
    assert cam.read_frame.call_count == 4
    cv2.destroyWindow.assert_called_once_with("Mark BED ROI")


def test_roi_marker_already_requested_shutdown_does_not_read_camera():
    cam, cv2 = Mock(), Mock()
    assert app._interactive_mark_bed_roi(cam, cv2, 1.0, Mock(), lambda: True) is False
    cam.read_frame.assert_not_called()
    cv2.destroyWindow.assert_not_called()
