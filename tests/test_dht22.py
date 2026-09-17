from __future__ import annotations

from sensors.dht22 import DHT22Reading, DHT22Sensor


def test_dht22_simulation_does_not_access_hardware():
    sensor = DHT22Sensor(data_pin=4, simulate=True)

    assert sensor.available is False
    assert sensor.read() is None


def test_dht22_reading_is_typed_value_container():
    reading = DHT22Reading(25.5, 60.0)

    assert reading.temperature_c == 25.5
    assert reading.humidity_pct == 60.0
