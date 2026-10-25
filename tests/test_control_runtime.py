"""Runtime telemetry must observe decisions and honour graceful stop requests."""

from __future__ import annotations

from contextlib import ExitStack
from threading import Event
from unittest.mock import Mock, patch

import config
import main as app
from core.state_machine import PostureState
from tests.test_runtime_regressions import _runtime_mocks
from vision.fall_classifier import FallFeatures


def test_status_callback_reports_decision_and_actual_gpio_mode_without_secrets():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        stack.enter_context(patch.object(app, "EventDB"))
        mocks["Camera"].read_frame.side_effect = [(True, Mock()), (False, None)]
        mocks["PoseEstimator"].extract_landmarks.return_value = [{"x": 0.5}] * 33
        mocks["PersonDetector"].has_person.return_value = True
        features = FallFeatures(70, 0.05, 0.4, 0.9, True, 0.6, hip_drop=0.2, recent_event=True)
        mocks["FallClassifier"].classify.return_value = (True, features)
        mocks["PostureStateMachine"].state = PostureState.NORMAL
        mocks["PostureStateMachine"].update.return_value = PostureState.FALLEN
        mocks["BuzzerLED"].simulate = True
        mocks["BuzzerLED"].active = True
        mocks["BuzzerLED"].led_active = False
        mocks["BuzzerLED"].led_2_active = True
        snapshots = []
        app.run(status_callback=snapshots.append)
        sample = next(snapshot for snapshot in snapshots if snapshot.get("camera_ok"))
        assert sample["state"] == "FALLEN"
        assert sample["hip_drop"] == 0.2
        assert sample["recent_event"] is True
        assert sample["gpio_simulated"] is True
        assert sample["buzzer_active"] is True
        assert sample["led_active"] is False
        assert sample["led_2_active"] is True
        assert sample["thresholds"]["FALL_SCORE_THRESHOLD"] == config.FALL_SCORE_THRESHOLD
        assert "LINE_CHANNEL_ACCESS_TOKEN" not in str(snapshots)
        assert snapshots[-1]["phase"] == "stopped"
        assert mocks["PostureStateMachine"].update.call_args.kwargs["fall_detected"] is True


def test_external_stop_request_runs_cleanup_without_reading_another_frame():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        db = stack.enter_context(patch.object(app, "EventDB")).return_value
        stop = Event()
        stop.set()
        app.run(stop_event=stop)
        mocks["Camera"].read_frame.assert_not_called()
        mocks["Camera"].release.assert_called_once()
        mocks["BuzzerLED"].close.assert_called_once()
        db.close.assert_called_once()
