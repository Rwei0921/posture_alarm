"""Standalone Buzzer/LED hardware test script."""

from __future__ import annotations

import argparse
import importlib
import time


DEFAULT_BUZZER_PIN = 17
DEFAULT_LED_PIN = 27


class SimulatedDevice:
    def __init__(self, name: str) -> None:
        self.name = name

    def on(self) -> None:
        print(f"{self.name}: ON")

    def off(self) -> None:
        print(f"{self.name}: OFF")

    def close(self) -> None:
        print(f"{self.name}: CLOSED")


def _build_devices(buzzer_pin: int, led_pin: int, simulate: bool):
    if simulate:
        return SimulatedDevice(f"Buzzer GPIO {buzzer_pin}"), SimulatedDevice(f"LED GPIO {led_pin}")

    try:
        gpiozero = importlib.import_module("gpiozero")
    except ImportError as exc:
        raise RuntimeError(
            "gpiozero is not installed. Run `pip install gpiozero` or use `--simulate`."
        ) from exc

    Buzzer = getattr(gpiozero, "Buzzer")
    LED = getattr(gpiozero, "LED")
    return Buzzer(buzzer_pin), LED(led_pin)


def _pulse(device, label: str, duration: float) -> None:
    print(f"Testing {label} for {duration:.1f}s")
    device.on()
    time.sleep(duration)
    device.off()
    time.sleep(0.3)


def run_test(buzzer_pin: int, led_pin: int, duration: float, repeat: int, simulate: bool) -> None:
    buzzer, led = _build_devices(buzzer_pin, led_pin, simulate)

    print("BZ/LED test starting")
    print(f"Buzzer: BCM GPIO {buzzer_pin}")
    print(f"LED: BCM GPIO {led_pin}")
    print("Press Ctrl+C to stop early")

    try:
        _pulse(led, "LED", duration)
        _pulse(buzzer, "Buzzer", duration)

        for index in range(repeat):
            print(f"Testing both devices blink {index + 1}/{repeat}")
            led.on()
            buzzer.on()
            time.sleep(duration)
            led.off()
            buzzer.off()
            time.sleep(duration)
    finally:
        buzzer.off()
        led.off()
        buzzer.close()
        led.close()
        print("BZ/LED test finished")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Buzzer and LED GPIO output.")
    parser.add_argument("--buzzer-pin", type=int, default=DEFAULT_BUZZER_PIN, help="BCM GPIO pin for buzzer")
    parser.add_argument("--led-pin", type=int, default=DEFAULT_LED_PIN, help="BCM GPIO pin for LED")
    parser.add_argument("--duration", type=float, default=0.5, help="On/off duration in seconds")
    parser.add_argument("--repeat", type=int, default=5, help="Blink repeat count for both devices")
    parser.add_argument("--simulate", action="store_true", help="Print actions without using GPIO hardware")
    args = parser.parse_args()

    run_test(
        buzzer_pin=args.buzzer_pin,
        led_pin=args.led_pin,
        duration=args.duration,
        repeat=args.repeat,
        simulate=args.simulate,
    )


if __name__ == "__main__":
    main()
