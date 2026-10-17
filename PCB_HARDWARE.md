# Existing PCB support

BCM outputs default to LED1 GPIO18, LED2 GPIO22, and buzzer GPIO17.
The SEA-1295Y passive 5V 50mA buzzer uses the existing 2N2222A driver;
keep `BUZZER_PWM_ENABLED=1` and `BUZZER_PWM_FREQUENCY=2000`.
No wiring changes are required.

The default environment backend is `ENV_SENSOR_BACKEND=sht31`.
Enable Raspberry Pi I2C and ensure the runtime user can access `/dev/i2c-1`.
The sensor uses Linux i2c-dev directly, with no additional Python packages.
`SHT31_I2C_BUS=1` and `SHT31_I2C_ADDRESS=0x44` select the PCB sensor;
the address can also be configured as `0x45` or a decimal integer.

Use `DHT22_FALLBACK_ENABLED=1` with `DHT22_ENABLED=1` to try the existing
DHT22 backend whenever an SHT31 sample fails. This requires the existing
DHT22 hardware and optional Adafruit dependency. Use
`ENV_SENSOR_BACKEND=dht22` for DHT22 alone, or `none` to disable sensing.
`ENV_READ_INTERVAL_SECONDS`, `ENV_LOG_INTERVAL_SECONDS`, and `ENV_SHOW`
control polling, logs, and overlay; their defaults retain the legacy DHT22
settings. Keep the read interval at least two seconds when using DHT22.
The last successful sample remains displayed and included in the existing
`temperature_c` and `humidity_pct` event payload fields after read failures.
Notification message formats are unchanged.

Run hardware diagnostics from the project environment:

```bash
python test_sht31.py --bus 1 --address 0x44
python test_sht31.py --simulate
python test_bz_led.py --pwm-buzzer --frequency 2000
```

Hardware tests access the existing PCB only when simulation is omitted.
