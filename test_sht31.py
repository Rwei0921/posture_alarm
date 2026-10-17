"""Standalone SHT31 temperature and humidity test script."""

from __future__ import annotations

import argparse
import time

from sensors.sht31 import SHT31Sensor


def main() -> None:
    parser = argparse.ArgumentParser(description="Read a SHT31 sensor on Raspberry Pi.")
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0x44)
    parser.add_argument("--reads", type=int, default=5, help="Number of readings")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between readings")
    parser.add_argument("--simulate", action="store_true", help="Skip physical sensor access")
    args = parser.parse_args()

    sensor = SHT31Sensor(bus=args.bus, address=args.address, simulate=args.simulate)
    try:
        if args.simulate:
            print("SHT31 simulation: physical read skipped")
            return
        if not sensor.available:
            raise SystemExit(f"SHT31 unavailable: {sensor.last_error or 'unknown error'}")

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
