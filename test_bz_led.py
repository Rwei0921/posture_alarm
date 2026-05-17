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

    def stop(self) -> None:
        self.off()


class SimulatedToneDevice(SimulatedDevice):
    def play(self, tone: float) -> None:
        print(f"{self.name}: TONE {tone:.0f}Hz")


def _build_devices(buzzer_pin: int, led_pin: int, simulate: bool, pwm_buzzer: bool):
    if simulate:
        buzzer = SimulatedToneDevice(f"Buzzer GPIO {buzzer_pin}") if pwm_buzzer else SimulatedDevice(f"Buzzer GPIO {buzzer_pin}")
        return buzzer, SimulatedDevice(f"LED GPIO {led_pin}")

    try:
        gpiozero = importlib.import_module("gpiozero")
    except ImportError as exc:
        raise RuntimeError(
            "gpiozero is not installed. Run `pip install gpiozero` or use `--simulate`."
        ) from exc

    Buzzer = getattr(gpiozero, "Buzzer")
    LED = getattr(gpiozero, "LED")
    TonalBuzzer = getattr(gpiozero, "TonalBuzzer")
    try:
        buzzer = TonalBuzzer(buzzer_pin) if pwm_buzzer else Buzzer(buzzer_pin)
        return buzzer, LED(led_pin)
    except Exception as exc:
        raise RuntimeError(
            "Unable to initialize Raspberry Pi GPIO. Install a pin factory and make sure "
            "the current user can access GPIO. Try: `sudo apt-get install -y python3-lgpio`, "
            "then `sudo usermod -aG gpio $USER`, log out/in or reboot, and run this script again. "
            "For a quick permission check, run with `sudo python test_bz_led.py`."
        ) from exc


def _pulse(device, label: str, duration: float) -> None:
    print(f"Testing {label} for {duration:.1f}s")
    device.on()
    time.sleep(duration)
    device.off()
    time.sleep(0.3)


def _tone(device, frequency: float, duration: float) -> None:
    print(f"Testing Buzzer tone at {frequency:.0f}Hz for {duration:.1f}s")
    device.play(frequency)
    time.sleep(duration)
    _stop_device(device)
    time.sleep(0.3)


def _stop_device(device) -> None:
    if hasattr(device, "stop"):
        device.stop()
    else:
        device.off()


def run_test(
    buzzer_pin: int,
    led_pin: int,
    duration: float,
    repeat: int,
    simulate: bool,
    pwm_buzzer: bool,
    frequency: float,
) -> None:
    buzzer, led = _build_devices(buzzer_pin, led_pin, simulate, pwm_buzzer)

    print("BZ/LED test starting")
    print(f"Buzzer: BCM GPIO {buzzer_pin}")
    print(f"LED: BCM GPIO {led_pin}")
    print("Press Ctrl+C to stop early")

    try:
        _pulse(led, "LED", duration)
        if pwm_buzzer:
            _tone(buzzer, frequency, duration)
        else:
            _pulse(buzzer, "Buzzer", duration)

        for index in range(repeat):
            print(f"Testing both devices blink {index + 1}/{repeat}")
            led.on()
            if pwm_buzzer:
                getattr(buzzer, "play")(frequency)
            else:
                buzzer.on()
            time.sleep(duration)
            led.off()
            _stop_device(buzzer)
            time.sleep(duration)
    finally:
        _stop_device(buzzer)
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
    parser.add_argument("--pwm-buzzer", action="store_true", help="Use PWM tone output for passive buzzers")
    parser.add_argument("--frequency", type=float, default=1000.0, help="PWM buzzer frequency in Hz")
    parser.add_argument("--simulate", action="store_true", help="Print actions without using GPIO hardware")
    args = parser.parse_args()

    run_test(
        buzzer_pin=args.buzzer_pin,
        led_pin=args.led_pin,
        duration=args.duration,
        repeat=args.repeat,
        simulate=args.simulate,
        pwm_buzzer=args.pwm_buzzer,
        frequency=args.frequency,
    )


if __name__ == "__main__":
    main()
