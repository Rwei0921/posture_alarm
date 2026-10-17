"""Run monitoring in a child process, leaving Tk on the parent main thread."""

from __future__ import annotations

import json
import signal
import sys
from threading import Event, Lock, Thread
import time
from typing import Any

from core.control_process import MESSAGE_PREFIX
from core.preview_stream import PreviewStream


def camera_preview(stop: Event, stream: PreviewStream, emit: Any) -> None:
    """ROI 設定階段僅開鏡頭，不載入模型、不啟動警報或通知。"""
    import config
    from vision.camera import Camera
    emit({"phase": "camera_preview", "camera_ok": False})
    camera = Camera(
        config.CAMERA_SOURCE, config.CAMERA_WIDTH, config.CAMERA_HEIGHT,
        backend=config.CAMERA_BACKEND, warmup_frames=config.CAMERA_WARMUP_FRAMES,
        read_retry=config.CAMERA_READ_RETRY, rpicam_fps=config.RPICAM_FPS,
        rpicam_timeout_ms=config.RPICAM_TIMEOUT_MS,
        rpicam_buffer_max_bytes=config.RPICAM_BUFFER_MAX_BYTES,
    )
    failures, last_status = 0, float("-inf")
    try:
        while not stop.is_set():
            stream.apply_pending()
            ok, frame = camera.read_frame()
            failures = 0 if ok else failures + 1
            now = time.monotonic()
            if now - last_status >= config.GUI_REFRESH_MS / 1000:
                emit({"phase": "camera_preview", "camera_ok": ok})
                last_status = now
            if ok:
                stream.offer(frame)
            elif failures >= config.CAMERA_MAX_READ_FAILURES:
                raise RuntimeError("Camera preview unavailable")
            stop.wait(0.01 if ok else 0.05)
    finally:
        camera.release()
        emit({"phase": "stopped", "camera_ok": False})


def worker(mode: str) -> int:
    stop = Event()
    output_lock = Lock()

    def send(message: dict[str, Any]) -> None:
        try:
            with output_lock:
                print(MESSAGE_PREFIX + json.dumps(message, ensure_ascii=True), flush=True)
        except (BrokenPipeError, OSError):
            stop.set()

    def emit(snapshot: dict[str, Any]) -> None:
        send({"type": "status", "data": snapshot})

    stream: PreviewStream | None = None

    def listen() -> None:
        # 管線結束代表控制面板已關閉，子程序也應清理硬體後離開。
        for line in sys.stdin:
            if line.strip() == "stop":
                break
            try:
                command = json.loads(line)
                if not isinstance(command, dict):
                    raise ValueError("Invalid command")
                assert stream is not None
                stream.command(command)
            except (ValueError, TypeError, OverflowError):
                send({"type": "command_error"})
        stop.set()

    try:
        import config
        if mode in {"monitor", "camera"}:
            emit({"phase": "camera_preview" if mode == "camera" else "starting", "camera_ok": False})
            from vision.camera import Camera
            # Windows 原生 NumPy/OpenCV 初始化可能檢查 stdin；先載入，避免與讀取管線的執行緒互鎖。
            Camera._load_cv2()
        stream = PreviewStream(config, send)
        Thread(target=listen, daemon=True).start()
        if mode == "monitor":
            from main import run
            run(status_callback=emit, stop_event=stop,
                frame_callback=stream.offer, control_callback=stream.apply_pending)
        elif mode == "camera":
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            camera_preview(stop, stream, emit)
        elif mode == "alarm_test":
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
        send({"type": "error", "error_type": type(exc).__name__})
        return 1
    finally:
        if stream is not None:
            stream.close()


if __name__ == "__main__":
    raise SystemExit(worker(sys.argv[1] if len(sys.argv) == 2 else "monitor"))
