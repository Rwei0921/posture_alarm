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
    ) -> None:
        self.simulate = simulate
        self.enabled = enabled
        self.buzzer_pwm = buzzer_pwm
        self.buzzer_frequency = buzzer_frequency
        self._active = False
        self._buzzer = None
        self._led = None

        if not self.simulate:
            try:
                gpiozero = importlib.import_module("gpiozero")
                Buzzer = getattr(gpiozero, "Buzzer")
                PWMOutputDevice = getattr(gpiozero, "PWMOutputDevice")
                LED = getattr(gpiozero, "LED")
                if self.buzzer_pwm:
                    self._buzzer = PWMOutputDevice(17, frequency=self.buzzer_frequency)
                else:
                    self._buzzer = Buzzer(17)
                self._led = LED(27)
            except Exception:
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
