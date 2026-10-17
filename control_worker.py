"""Run monitoring in a child process, leaving Tk on the parent main thread."""

from __future__ import annotations

import json
import signal
import sys
from threading import Event, Thread
from typing import Any

from core.control_process import MESSAGE_PREFIX


def worker(mode: str) -> int:
    stop = Event()

    def emit(snapshot: dict[str, Any]) -> None:
        try:
            print(MESSAGE_PREFIX + json.dumps({"type": "status", "data": snapshot}, ensure_ascii=True), flush=True)
        except (BrokenPipeError, OSError):
            stop.set()

    def listen() -> None:
        # 管線結束代表控制面板已關閉，子程序也應清理硬體後離開。
        for line in sys.stdin:
            if line.strip() == "stop":
                break
        stop.set()

    Thread(target=listen, daemon=True).start()
    try:
        if mode == "monitor":
            from main import run
            run(status_callback=emit, stop_event=stop)
        elif mode == "alarm_test":
            import config
            from alert.buzzer_led import BuzzerLED
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            alarm = BuzzerLED(
                simulate=config.SIMULATE_GPIO,
                buzzer_pwm=config.BUZZER_PWM_ENABLED, buzzer_frequency=config.BUZZER_PWM_FREQUENCY,
                buzzer_pin=config.BUZZER_GPIO_PIN, led_pin=config.LED_GPIO_PIN,
                led_2_pin=config.LED_2_GPIO_PIN, led_2_enabled=config.LED_2_ENABLED,
            )
            try:
                if not stop.is_set():
                    alarm.alert_on()
                    emit({"phase": "alarm_test", "gpio_simulated": alarm.simulate,
                          "buzzer_active": alarm.active, "led_active": alarm.active,
                          "led_2_active": alarm.active and config.LED_2_ENABLED})
                    stop.wait(1.0)
            finally:
                alarm.close()
                emit({"phase": "stopped", "camera_ok": False})
        else:
            raise ValueError("Unknown worker mode")
        return 0
    except Exception as exc:
        # 不傳回例外全文，避免連線錯誤中的 Token、Webhook 或設定值外洩。
        print(MESSAGE_PREFIX + json.dumps({"type": "error", "error_type": type(exc).__name__}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(worker(sys.argv[1] if len(sys.argv) == 2 else "monitor"))
