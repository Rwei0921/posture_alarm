"""Standalone DHT22 temperature and humidity test script."""

from __future__ import annotations

import argparse
import time

from sensors.dht22 import DHT22Sensor


def main() -> None:
    parser = argparse.ArgumentParser(description="Read a DHT22 sensor on Raspberry Pi.")
    parser.add_argument("--data-pin", type=int, default=4, help="BCM GPIO pin for DHT22 DATA")
    parser.add_argument("--reads", type=int, default=5, help="Number of readings")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between readings")
    parser.add_argument("--simulate", action="store_true", help="Skip physical sensor access")
    args = parser.parse_args()

    sensor = DHT22Sensor(data_pin=args.data_pin, simulate=args.simulate, use_pulseio=False)
    try:
        if args.simulate:
            print("DHT22 simulation: physical read skipped")
            return
        if not sensor.available:
            raise SystemExit(f"DHT22 unavailable: {sensor.last_error or 'unknown error'}")

        for index in range(max(1, args.reads)):
            reading = sensor.read()
            if reading is None:
                print(f"Read {index + 1}: failed - {sensor.last_error or 'unknown error'}")
            else:
                print(
                    f"Read {index + 1}: temperature={reading.temperature_c:.1f}C "
                    f"humidity={reading.humidity_pct:.1f}%"
                )
            if index + 1 < max(1, args.reads):
                time.sleep(max(0.1, args.interval))
    finally:
        sensor.close()


if __name__ == "__main__":
    main()
