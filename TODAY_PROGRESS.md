# Today Progress

Date: 2026-05-17

## Completed

- Confirmed Buzzer and LED wiring pins:
  - Buzzer: BCM GPIO 17, physical pin 11
  - LED: BCM GPIO 27, physical pin 13
- Changed GPIO runtime from simulation-first to real hardware by default.
- Added `test_bz_led.py` for standalone LED and buzzer testing.
- Added PWM buzzer support for the two-pin passive buzzer.
- Updated the main alarm path to use PWM buzzer output by default at 2000 Hz.
- Added file logging support with `LOG_FILE_ENABLED` and `LOG_FILE_PATH`.
- Allowed `LOG_FILE_PATH` to be either a file path or a directory path.
- Added startup logging for GPIO, LINE, Discord, and log-file status.
- Added `setup_demo.py` for simple demo setup without editing system files.
- Added `run_demo.sh` to load `demo.env` and start the app.
- Added `test_notify.py` to test LINE and Discord directly without waiting for a fall event.
- Added `posture_alarm.env.example` for systemd deployments.
- Added `.gitignore` to keep caches, runtime data, virtualenvs, and `demo.env` out of git.
- Removed unused generated files and old artifacts:
  - tracked `__pycache__` files
  - old report PDF/PPTX/DOCX/Marp files
  - old `extract_docx.py`
  - old `structure.txt`

## Verified

- Buzzer/LED test script supports simulation, ON/OFF mode, and PWM mode.
- LINE notification test reached HTTP 200 in Raspberry Pi testing.
- Discord test now validates webhook URL format before sending.
- Unit tests pass locally after the changes.

## Current Usage

For demo use:

```bash
python setup_demo.py
./run_demo.sh
```

For standalone hardware test:

```bash
python test_bz_led.py --pwm-buzzer --frequency 2000 --duration 2 --repeat 3
```

For standalone notification test:

```bash
python test_notify.py
```

## Notes

- `demo.env` is intentionally ignored by git because it can contain LINE tokens and Discord webhook URLs.
- The Discord webhook must look like `https://discord.com/api/webhooks/...`; placeholder URLs such as `https://test.com` are rejected.
