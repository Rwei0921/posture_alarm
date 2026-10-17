"""Hardware-free SHT31 and fallback coverage without pytest fixtures."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sensors.dht22 import DHT22Reading
from sensors.environment import EnvironmentSensor
from sensors.sht31 import SHT31Sensor


def test_simulation_never_opens_hardware():
    with patch("builtins.open", side_effect=AssertionError("hardware accessed")):
        sensor = SHT31Sensor(simulate=True)
        assert not sensor.available
        assert sensor.read() is None
        sensor.close()


def test_i2c_bus_address_conversion_and_cleanup():
    device = Mock()
    # Sensirion CRC example: CRC(0xBEEF) == 0x92.
    assert SHT31Sensor._crc(b"\xbe\xef") == 0x92
    data = b"\x66\x66"
    word = data + bytes([SHT31Sensor._crc(data)])
    device.read.return_value = word + word
    # 模擬 Linux I²C 邊界，讓無硬體的 Windows 測試也能驗證相同操作。
    ioctl = Mock()
    with patch("builtins.open", return_value=device) as opener, patch.dict(sys.modules, {"fcntl": SimpleNamespace(ioctl=ioctl)}):
        sensor = SHT31Sensor(bus=1, address=0x45)
        opener.assert_called_once_with("/dev/i2c-1", "r+b", buffering=0)
        ioctl.assert_called_once_with(device.fileno(), 0x0703, 0x45)
        with patch("sensors.sht31.time.sleep"):
            reading = sensor.read()
        assert reading is not None
        assert abs(reading.temperature_c - 25.0) < 0.01
        assert abs(reading.humidity_pct - 40.0) < 0.01
        device.write.assert_called_once_with(b"\x24\x00")
        sensor.close()
        sensor.close()
        device.close.assert_called_once()
        assert not sensor.available


def test_bad_reads_fail_soft_and_recover():
    sensor = SHT31Sensor(simulate=True)
    device = Mock()
    sensor._device = device
    with patch("sensors.sht31.time.sleep"):
        for response in (b"", b"\x00" * 6):
            device.read.return_value = response
            assert sensor.read() is None
            assert "CRC" in sensor.last_error
        device.write.side_effect = OSError("disconnected")
        assert sensor.read() is None
        assert "disconnected" in sensor.last_error
        device.write.side_effect = None
        word = b"\x00\x00" + bytes([SHT31Sensor._crc(b"\x00\x00")])
        device.read.return_value = word * 2
        assert sensor.read() == DHT22Reading(-45.0, 0.0)
        assert sensor.last_error is None


def test_initialization_failure_closes_bus():
    device = Mock()
    ioctl = Mock(side_effect=OSError("no device"))
    with patch("builtins.open", return_value=device), patch.dict(sys.modules, {"fcntl": SimpleNamespace(ioctl=ioctl)}):
        sensor = SHT31Sensor()
        assert not sensor.available
        assert "no device" in sensor.last_error
        device.close.assert_called_once()


def test_fallback_on_missing_sensor_and_transient_failure():
    primary, fallback = Mock(), Mock()
    primary.available = False
    primary.read.return_value = None
    fallback.available = True
    fallback.read.return_value = DHT22Reading(22.0, 55.0)
    sensor = EnvironmentSensor(primary, fallback)
    assert sensor.available
    assert sensor.read() == DHT22Reading(22.0, 55.0)
    primary.read.return_value = DHT22Reading(23.0, 56.0)
    assert sensor.read() == DHT22Reading(23.0, 56.0)
    assert fallback.read.call_count == 1
    sensor.close()
    primary.close.assert_called_once()
    fallback.close.assert_called_once()
