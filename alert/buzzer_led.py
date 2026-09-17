"""Buzzer/LED alarm controller with simulation mode."""

from __future__ import annotations

import importlib
import time


class BuzzerLED:
    def __init__(
        self,
        simulate: bool = True,
        enabled: bool = True,
        buzzer_pwm: bool = True,
        buzzer_frequency: float = 2000.0,
        buzzer_pin: int = 17,
        led_pin: int = 27,
        led_2_pin: int = 22,
        led_2_enabled: bool = True,
    ) -> None:
        self.simulate = simulate
        self.enabled = enabled
        self.buzzer_pwm = buzzer_pwm
        self.buzzer_frequency = buzzer_frequency
        self.buzzer_pin = buzzer_pin
        self.led_pin = led_pin
        self.led_2_pin = led_2_pin
        self.led_2_enabled = led_2_enabled
        self._active = False
        self._buzzer = None
        self._led = None
        self._led_2 = None

        if not self.simulate:
            try:
                gpiozero = importlib.import_module("gpiozero")
                Buzzer = getattr(gpiozero, "Buzzer")
                PWMOutputDevice = getattr(gpiozero, "PWMOutputDevice")
                LED = getattr(gpiozero, "LED")
                if self.buzzer_pwm:
                    self._buzzer = PWMOutputDevice(self.buzzer_pin, frequency=self.buzzer_frequency)
                else:
                    self._buzzer = Buzzer(self.buzzer_pin)
                self._led = LED(self.led_pin)
                if self.led_2_enabled:
                    self._led_2 = LED(self.led_2_pin)
            except Exception:
                for device in (self._buzzer, self._led, self._led_2):
                    if device is not None:
                        try:
                            device.close()
                        except Exception:
                            pass
                self._buzzer = None
                self._led = None
                self._led_2 = None
                self.simulate = True

    @property
    def active(self) -> bool:
        return self._active

    def alert_on(self) -> None:
        if not self.enabled:
            return
        self._active = True
        if self.simulate:
            return
        if self._buzzer is not None:
            if self.buzzer_pwm:
                self._buzzer.value = 0.5
            else:
                self._buzzer.on()
        if self._led is not None:
            self._led.on()
        if self._led_2 is not None:
            self._led_2.on()

    def alert_off(self) -> None:
        self._active = False
        if self.simulate:
            return
        if self._buzzer is not None:
            if self.buzzer_pwm:
                self._buzzer.value = 0.0
            else:
                self._buzzer.off()
        if self._led is not None:
            self._led.off()
        if self._led_2 is not None:
            self._led_2.off()

    def pulse(self, duration: float = 1.0, interval: float = 0.2) -> None:
        if not self.enabled:
            return
        end = time.monotonic() + duration
        while time.monotonic() < end:
            self.alert_on()
            time.sleep(interval)
            self.alert_off()
            time.sleep(interval)

    def close(self) -> None:
        self.alert_off()
        for device in (self._buzzer, self._led, self._led_2):
            if device is not None:
                device.close()
