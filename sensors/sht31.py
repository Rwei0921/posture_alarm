"""Fail-soft SHT31 boundary using Linux i2c-dev without extra dependencies."""

from __future__ import annotations

import importlib
import time
from typing import Any

from sensors.dht22 import DHT22Reading


class SHT31Sensor:
    def __init__(self, bus: int = 1, address: int = 0x44, simulate: bool = False) -> None:
        self._device: Any | None = None
        self._last_error: str | None = None
        if simulate:
            return
        try:
            if bus < 0 or address not in (0x44, 0x45):
                raise ValueError("SHT31 requires a nonnegative bus and address 0x44 or 0x45")
            fcntl = importlib.import_module("fcntl")
            self._device = open(f"/dev/i2c-{bus}", "r+b", buffering=0)
            fcntl.ioctl(self._device.fileno(), 0x0703, address)
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self.close()

    @property
    def available(self) -> bool:
        return self._device is not None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @staticmethod
    def _crc(data: bytes) -> int:
        crc = 0xFF
        for value in data:
            crc ^= value
            for _ in range(8):
                crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return crc

    def read(self) -> DHT22Reading | None:
        if self._device is None:
            return None
        try:
            self._device.write(b"\x24\x00")  # Single shot, high repeatability, no clock stretching.
            time.sleep(0.016)
            data = self._device.read(6)
            if len(data) != 6 or self._crc(data[:2]) != data[2] or self._crc(data[3:5]) != data[5]:
                raise ValueError("SHT31 short response or CRC mismatch")
            reading = DHT22Reading(
                -45.0 + 175.0 * int.from_bytes(data[:2], "big") / 65535.0,
                100.0 * int.from_bytes(data[3:5], "big") / 65535.0,
            )
            self._last_error = None
            return reading
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            return None

    def close(self) -> None:
        device, self._device = self._device, None
        if device is not None:
            try:
                device.close()
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
