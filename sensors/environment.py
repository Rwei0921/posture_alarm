"""Select the environment sensor and optional DHT22 fallback."""

from __future__ import annotations

from sensors.dht22 import DHT22Reading, DHT22Sensor
from sensors.sht31 import SHT31Sensor


class EnvironmentSensor:
    def __init__(self, primary: SHT31Sensor | DHT22Sensor, fallback: DHT22Sensor | None = None) -> None:
        self.primary = primary
        self.fallback = fallback

    @property
    def available(self) -> bool:
        return self.primary.available or bool(self.fallback and self.fallback.available)

    @property
    def last_error(self) -> str | None:
        errors = [sensor.last_error for sensor in (self.primary, self.fallback) if sensor and sensor.last_error]
        return "; ".join(errors) or None

    def read(self) -> DHT22Reading | None:
        reading = self.primary.read()
        if reading is None and self.fallback is not None:
            return self.fallback.read()
        return reading

    def close(self) -> None:
        try:
            self.primary.close()
        finally:
            if self.fallback is not None:
                self.fallback.close()
