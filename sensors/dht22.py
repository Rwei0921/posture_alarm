"""Fail-soft DHT22 temperature and humidity sensor boundary."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DHT22Reading:
    """One valid DHT22 sample."""

    temperature_c: float
    humidity_pct: float


class DHT22Sensor:
    """Read a DHT22 through Adafruit Blinka on Raspberry Pi."""

    def __init__(
        self,
        data_pin: int = 4,
        simulate: bool = False,
        use_pulseio: bool = False,
    ) -> None:
        self.data_pin = data_pin
        self.simulate = simulate
        self.use_pulseio = use_pulseio
        self._device: Any | None = None
        self._last_error: str | None = None

        if self.simulate:
            return

        try:
            board = importlib.import_module("board")
            adafruit_dht = importlib.import_module("adafruit_dht")
            board_pin = getattr(board, f"D{self.data_pin}")
            self._device = adafruit_dht.DHT22(
                board_pin,
                use_pulseio=self.use_pulseio,
            )
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"

    @property
    def available(self) -> bool:
        return self._device is not None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def read(self) -> DHT22Reading | None:
        """Return the latest sample, or None when the hardware read fails."""
        if self._device is None:
            return None

        try:
            temperature_c = self._device.temperature
            humidity_pct = self._device.humidity
            if temperature_c is None or humidity_pct is None:
                self._last_error = "DHT22 returned an empty reading"
                return None
            self._last_error = None
            return DHT22Reading(float(temperature_c), float(humidity_pct))
        except Exception as exc:
            # DHT sensors can report transient RuntimeError values; the main
            # loop keeps running and retries at the configured interval.
            self._last_error = f"{type(exc).__name__}: {exc}"
            return None

    def close(self) -> None:
        if self._device is None:
            return
        exit_method = getattr(self._device, "exit", None)
        if callable(exit_method):
            exit_method()
        else:
            close_method = getattr(self._device, "close", None)
            if callable(close_method):
                close_method()
