"""Buzzer and separate normal/alarm LEDs with simulation mode."""

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
        led_pin: int = 18,
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
        self._led_active = False
        self._led_2_active = False
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

    @property
    def led_active(self) -> bool:
        """綠燈的輸出命令；模擬模式不代表實體燈已亮起。"""
        return self._led_active

    @property
    def led_2_active(self) -> bool:
        """紅燈的輸出命令，與綠燈分開回報給 GUI。"""
        return self._led_2_active

    def indicators_off(self) -> None:
        """影像暫時中斷時熄滅兩燈，但不擅自解除既有蜂鳴器警報。"""
        self._led_active = False
        self._led_2_active = False
        if self.simulate:
            return
        if self._led is not None:
            self._led.off()
        if self._led_2 is not None:
            self._led_2.off()

    def normal_on(self) -> None:
        """成功完成一幀偵測且沒有確認跌倒時，只亮綠燈。"""
        # 連續正常的影格保持常亮，不要每幀先熄燈再重亮。
        if not self.enabled or self._led_active:
            return
        self.alert_off()
        self._led_active = True
        if not self.simulate and self._led is not None:
            self._led.on()

    def alert_on(self) -> None:
        if not self.enabled:
            return
        # 確認跌倒後關閉正常指示，紅燈與蜂鳴器才是警報輸出。
        self._active = True
        self._led_active = False
        self._led_2_active = self.led_2_enabled
        if self.simulate:
            return
        if self._led is not None:
            self._led.off()
        if self._buzzer is not None:
            if self.buzzer_pwm:
                self._buzzer.value = 0.5
            else:
                self._buzzer.on()
        if self._led_2 is not None:
            self._led_2.on()

    def alert_off(self) -> None:
        self._active = False
        self.indicators_off()
        if self.simulate:
            return
        if self._buzzer is not None:
            if self.buzzer_pwm:
                self._buzzer.value = 0.0
            else:
                self._buzzer.off()

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
