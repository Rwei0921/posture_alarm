"""PCB defaults and environment overlay checks without hardware fixtures."""

from __future__ import annotations

import importlib
from unittest.mock import Mock, patch

import config
from alert.buzzer_led import BuzzerLED
from ui.overlay import Overlay


def test_pcb_defaults_and_hex_address_override():
    with patch.dict("os.environ", {}, clear=True):
        importlib.reload(config)
        assert (config.LED_GPIO_PIN, config.LED_2_GPIO_PIN, config.BUZZER_GPIO_PIN) == (18, 22, 17)
        assert config.BUZZER_PWM_ENABLED
        assert config.BUZZER_PWM_FREQUENCY == 2000
        assert config.SHT31_I2C_BUS == 1
        assert config.SHT31_I2C_ADDRESS == 0x44
        assert config.ENV_SENSOR_BACKEND == "sht31"
        assert not config.DHT22_FALLBACK_ENABLED
    with patch.dict("os.environ", {"SHT31_I2C_ADDRESS": "0x45"}):
        importlib.reload(config)
        assert config.SHT31_I2C_ADDRESS == 0x45
    importlib.reload(config)


def test_buzzer_uses_pwm_and_pcb_leds():
    gpio = Mock()
    with patch("alert.buzzer_led.importlib.import_module", return_value=gpio):
        alarm = BuzzerLED(simulate=False)
        gpio.PWMOutputDevice.assert_called_once_with(17, frequency=2000.0)
        assert [call.args for call in gpio.LED.call_args_list] == [(18,), (22,)]
        alarm.alert_on()
        assert gpio.PWMOutputDevice.return_value.value == 0.5
        alarm.close()
        assert gpio.PWMOutputDevice.return_value.value == 0.0


def test_overlay_handles_missing_and_valid_environment():
    cv2 = Mock()
    overlay = Overlay()
    with patch.object(Overlay, "_load_cv2", return_value=cv2):
        frame = object()
        assert overlay.draw_environment(frame, None, None) is frame
        assert cv2.putText.call_args.args[1] == "Environment: unavailable"
        overlay.draw_environment(frame, 25.0, 60.0)
        assert cv2.putText.call_args.args[1] == "Temp: 25.0C  Humidity: 60.0%"
