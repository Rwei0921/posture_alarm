"""Normal/alarm indicator regressions without real GPIO, cameras or notifications."""

from __future__ import annotations

from contextlib import ExitStack
import io
import json
from unittest.mock import Mock, patch

import pytest

import config
import control_worker
import main as app
from alert.buzzer_led import BuzzerLED
from core.control_process import MESSAGE_PREFIX
from core.state_machine import PostureState
from tests.test_runtime_regressions import _runtime_mocks


def outputs(alarm: BuzzerLED) -> tuple[bool, bool, bool]:
    return alarm.led_active, alarm.led_2_active, alarm.active


@pytest.mark.parametrize("pwm", [True, False])
def test_gpio_outputs_distinguish_normal_alarm_recovery_and_shutdown(pwm):
    gpio, green, red = Mock(), Mock(), Mock()
    gpio.LED.side_effect = [green, red]
    with patch("alert.buzzer_led.importlib.import_module", return_value=gpio):
        alarm = BuzzerLED(simulate=False, buzzer_pwm=pwm)
    buzzer = gpio.PWMOutputDevice.return_value if pwm else gpio.Buzzer.return_value
    assert [call.args for call in gpio.LED.call_args_list] == [(18,), (22,)]
    assert outputs(alarm) == (False, False, False)

    alarm.normal_on()
    assert outputs(alarm) == (True, False, False)
    green.on.assert_called_once()
    red.on.assert_not_called()
    if pwm:
        assert buzzer.value == 0.0
    else:
        buzzer.on.assert_not_called()
    green_off_count = green.off.call_count
    alarm.normal_on()
    assert green.off.call_count == green_off_count

    alarm.alert_on()
    assert outputs(alarm) == (False, True, True)
    green.off.assert_called()
    red.on.assert_called_once()
    if pwm:
        assert buzzer.value == 0.5
    else:
        buzzer.on.assert_called_once()

    # 影像中斷只熄燈，不把已確認的跌倒當成已恢復。
    alarm.indicators_off()
    assert outputs(alarm) == (False, False, True)
    if pwm:
        assert buzzer.value == 0.5

    alarm.normal_on()
    assert outputs(alarm) == (True, False, False)
    alarm.close()
    assert outputs(alarm) == (False, False, False)
    for device in (green, red, buzzer):
        device.close.assert_called_once()
    if pwm:
        assert buzzer.value == 0.0


def test_simulated_indicators_and_disabled_red_led():
    alarm = BuzzerLED(simulate=True, led_2_enabled=False)
    alarm.normal_on()
    assert outputs(alarm) == (True, False, False)
    alarm.alert_on()
    assert outputs(alarm) == (False, False, True)
    alarm.close()
    assert outputs(alarm) == (False, False, False)


def test_disabled_outputs_never_claim_a_lit_led_or_active_buzzer():
    alarm = BuzzerLED(simulate=True, enabled=False)
    alarm.normal_on()
    alarm.alert_on()
    assert outputs(alarm) == (False, False, False)
    alarm.close()


def test_disabled_red_does_not_allocate_or_drive_its_pin():
    gpio = Mock()
    with patch("alert.buzzer_led.importlib.import_module", return_value=gpio):
        alarm = BuzzerLED(simulate=False, led_2_enabled=False)
    gpio.LED.assert_called_once_with(18)
    alarm.alert_on()
    assert outputs(alarm) == (False, False, True)
    gpio.LED.return_value.on.assert_not_called()
    alarm.close()


def test_gpio_failure_closes_partial_devices_and_falls_back_to_simulation():
    gpio, green = Mock(), Mock()
    gpio.LED.side_effect = [green, RuntimeError("GPIO unavailable")]
    with patch("alert.buzzer_led.importlib.import_module", return_value=gpio):
        alarm = BuzzerLED(simulate=False)
    assert alarm.simulate is True
    green.close.assert_called_once()
    gpio.PWMOutputDevice.return_value.close.assert_called_once()
    alarm.normal_on()
    assert outputs(alarm) == (True, False, False)
    green.on.assert_not_called()
    alarm.close()


@pytest.mark.parametrize("state", list(PostureState))
def test_runtime_reports_separate_led_commands_without_changing_fall_notifications(state):
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        stack.enter_context(patch.object(app, "EventDB"))
        alarm = BuzzerLED(simulate=True)
        stack.enter_context(patch.object(app, "BuzzerLED", return_value=alarm))
        mocks["Camera"].read_frame.side_effect = [(True, Mock()), (False, None)]
        mocks["PoseEstimator"].extract_landmarks.return_value = []
        mocks["PostureStateMachine"].state = state
        mocks["PostureStateMachine"].update.return_value = state
        snapshots = []
        app.run(status_callback=snapshots.append)

        sample = next(item for item in snapshots if item.get("camera_ok"))
        fallen = state == PostureState.FALLEN
        assert sample["led_active"] is (not fallen)
        assert sample["led_2_active"] is fallen
        assert sample["buzzer_active"] is fallen
        assert sample["person_present"] is False
        failed_frame = next(item for item in snapshots if "read_failures" in item)
        assert failed_frame["led_active"] is False
        assert failed_frame["led_2_active"] is False
        assert failed_frame["buzzer_active"] is fallen
        assert outputs(alarm) == (False, False, False)
        assert mocks["LineNotifier"].send.call_count == int(fallen)
        assert mocks["DiscordNotifier"].send.call_count == int(fallen)


def test_green_resumes_after_a_temporary_camera_failure():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        stack.enter_context(patch.object(config, "CAMERA_MAX_READ_FAILURES", 2))
        stack.enter_context(patch.object(config, "GUI_REFRESH_MS", 0))
        stack.enter_context(patch.object(app, "EventDB"))
        alarm = BuzzerLED(simulate=True)
        stack.enter_context(patch.object(app, "BuzzerLED", return_value=alarm))
        mocks["Camera"].read_frame.side_effect = [
            (True, Mock()), (False, None), (True, Mock()), (False, None), (False, None),
        ]
        mocks["PoseEstimator"].extract_landmarks.return_value = []
        mocks["PostureStateMachine"].state = PostureState.NORMAL
        mocks["PostureStateMachine"].update.return_value = PostureState.NORMAL
        snapshots = []
        app.run(status_callback=snapshots.append)
        running = [item for item in snapshots if item["phase"] == "running"]
        assert [item["led_active"] for item in running] == [True, False, True, False, False]
        assert not any(item["led_2_active"] for item in running)
        assert mocks["PostureStateMachine"].update.call_count == 2
        assert outputs(alarm) == (False, False, False)


@pytest.mark.parametrize("failure", ["inference", "camera_release"])
def test_runtime_clears_indicators_even_when_detection_or_camera_cleanup_raises(failure):
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        stack.enter_context(patch.object(app, "EventDB"))
        alarm = BuzzerLED(simulate=True)
        stack.enter_context(patch.object(app, "BuzzerLED", return_value=alarm))
        mocks["PostureStateMachine"].state = PostureState.NORMAL
        mocks["PostureStateMachine"].update.return_value = PostureState.NORMAL
        if failure == "inference":
            mocks["Camera"].read_frame.side_effect = [(True, Mock()), (True, Mock())]
            mocks["PoseEstimator"].extract_landmarks.side_effect = [[], RuntimeError("inference")]
        else:
            mocks["Camera"].read_frame.side_effect = [(True, Mock()), (False, None)]
            mocks["PoseEstimator"].extract_landmarks.return_value = []
            mocks["Camera"].release.side_effect = RuntimeError("camera_release")
        snapshots = []
        with pytest.raises(RuntimeError, match=failure):
            app.run(status_callback=snapshots.append)
        assert any(item.get("led_active") for item in snapshots)
        assert outputs(alarm) == (False, False, False)


def test_manual_opencv_roi_marker_does_not_leave_green_on_while_detection_is_paused():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        stack.enter_context(patch.object(config, "SHOW_WINDOW", True))
        stack.enter_context(patch.object(app, "EventDB"))
        alarm = BuzzerLED(simulate=True)
        stack.enter_context(patch.object(app, "BuzzerLED", return_value=alarm))
        mocks["Camera"].read_frame.return_value = (True, Mock())
        mocks["PoseEstimator"].extract_landmarks.return_value = []
        mocks["PostureStateMachine"].state = PostureState.NORMAL
        mocks["PostureStateMachine"].update.return_value = PostureState.NORMAL
        cv2 = stack.enter_context(patch.object(app, "_load_cv2")).return_value
        cv2.waitKey.return_value = ord("m")

        def mark(*_args):
            assert outputs(alarm) == (False, False, False)
            return False

        marker = stack.enter_context(patch.object(app, "_interactive_mark_bed_roi", side_effect=mark))
        app.run()
        marker.assert_called_once()


def test_gpio_cleanup_failure_still_releases_camera_models_and_database():
    with ExitStack() as stack:
        mocks = _runtime_mocks(stack)
        stack.enter_context(patch.object(config, "ENV_SENSOR_BACKEND", "none"))
        db = stack.enter_context(patch.object(app, "EventDB")).return_value
        mocks["Camera"].read_frame.return_value = (False, None)
        mocks["BuzzerLED"].close.side_effect = RuntimeError("GPIO close failed")
        with pytest.raises(RuntimeError, match="GPIO close failed"):
            app.run()
        for name in ("PoseEstimator", "PersonDetector"):
            mocks[name].close.assert_called_once()
        mocks["Camera"].release.assert_called_once()
        db.close.assert_called_once()


@pytest.mark.parametrize("cancel_after_green", [False, True])
def test_gui_hardware_test_checks_green_then_red_and_handles_stop(cancel_after_green):
    output, stop = io.StringIO(), Mock()
    stop.is_set.return_value = False
    if cancel_after_green:
        stop.wait.side_effect = lambda _seconds: setattr(stop.is_set, "return_value", True)
    alarm = BuzzerLED(simulate=True)
    with patch("control_worker.Event", return_value=stop), patch("control_worker.Thread"), \
            patch("control_worker.PreviewStream"), patch("control_worker.signal.signal"), \
            patch("alert.buzzer_led.BuzzerLED", return_value=alarm), patch("sys.stdout", output):
        assert control_worker.worker("alarm_test") == 0
    messages = [json.loads(line[len(MESSAGE_PREFIX):]) for line in output.getvalue().splitlines()]
    samples = [item["data"] for item in messages if item["data"]["phase"] == "alarm_test"]
    expected = [(True, False, False)]
    if not cancel_after_green:
        expected.append((False, True, True))
    assert [(item["led_active"], item["led_2_active"], item["buzzer_active"]) for item in samples] == expected
    assert samples[0]["hardware"]["led_pin"] == config.LED_GPIO_PIN
    assert samples[0]["hardware"]["led_2_pin"] == config.LED_2_GPIO_PIN
    assert messages[-1]["data"]["phase"] == "stopped"
    assert outputs(alarm) == (False, False, False)
