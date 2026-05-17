# Posture Alarm

`posture_alarm` is a Raspberry Pi posture alarm demo. It uses a camera and MediaPipe Pose to detect fall-like posture, then triggers LED, buzzer, LINE, Discord, SQLite logging, and on-screen overlay.

## Hardware Pins

Use BCM GPIO numbering:

| Device | BCM GPIO | Physical Pin |
| --- | --- | --- |
| Buzzer | GPIO 17 | Pin 11 |
| LED | GPIO 27 | Pin 13 |

LED should use a resistor, typically 220 to 330 ohm. The current buzzer flow uses PWM by default for a two-pin passive buzzer.

## Install On Raspberry Pi

```bash
cd /home/pi/posture_alarm
./install_rpi.sh
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If GPIO cannot initialize, install the GPIO backend:

```bash
sudo apt-get update
sudo apt-get install -y python3-lgpio
sudo usermod -aG gpio $USER
sudo reboot
```

## Demo Setup

For public demos, use the guided setup:

```bash
cd /home/pi/posture_alarm
source .venv/bin/activate
python setup_demo.py
./run_demo.sh
```

`setup_demo.py` creates `demo.env`. This file stores demo settings such as GPIO mode, buzzer frequency, LINE token, Discord webhook, and log path. It is ignored by git.

If `run_demo.sh` is not executable:

```bash
chmod +x run_demo.sh
./run_demo.sh
```

## Manual Run

```bash
cd /home/pi/posture_alarm
source .venv/bin/activate
python main.py
```

If you want to load `demo.env` manually:

```bash
set -a
source demo.env
set +a
python main.py
```

## Systemd Run

Copy the service and create an environment file:

```bash
sudo cp posture_alarm.service /etc/systemd/system/posture_alarm.service
sudo cp posture_alarm.env.example /etc/posture_alarm.env
sudo nano /etc/posture_alarm.env
```

Then start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable posture_alarm
sudo systemctl restart posture_alarm
```

View service logs:

```bash
journalctl -u posture_alarm -f
```

## Test Hardware

Test LED and buzzer without running the full app:

```bash
python test_bz_led.py --pwm-buzzer --frequency 2000 --duration 2 --repeat 3
```

If you only want to check the script flow without GPIO hardware:

```bash
python test_bz_led.py --simulate --pwm-buzzer
```

## Test LINE And Discord

After `demo.env` is configured:

```bash
python test_notify.py
```

Expected success examples:

```text
LINE: HTTP 200
Discord: HTTP 204
Result: line=True discord=True
```

Common failures:

| Output | Meaning |
| --- | --- |
| `LINE: skipped` | LINE token or target id is empty |
| `LINE: HTTP 400` | LINE target id is likely wrong |
| `LINE: HTTP 401` | LINE token is likely wrong |
| `Discord: skipped` | Discord webhook is empty |
| `Discord: suspicious webhook host` | Discord webhook is not a Discord URL |
| `Discord: HTTP 404` | Discord webhook is wrong or deleted |

## Logs

File logging is enabled by default. The default path is:

```bash
data/posture_alarm.log
```

If `LOG_FILE_PATH` is set to a directory, the app writes `posture_alarm.log` inside that directory.

Example:

```env
LOG_FILE_PATH=/home/pi/Desktop/LOG_DATA
```

Actual log file:

```bash
/home/pi/Desktop/LOG_DATA/posture_alarm.log
```

View logs:

```bash
tail -f /home/pi/posture_alarm/data/posture_alarm.log
```

## Bed ROI Marking

Run the ROI marker:

```bash
python mark_bed_roi.py
```

Mark ROI and then start the app:

```bash
python mark_bed_roi.py --run-main
```

The demo setup can also enable bed marking on startup.

## Test Suite

```bash
python -m pytest tests -q
```

Import health check:

```bash
python -c "from vision.camera import Camera; from vision.person_detector import PersonDetector; from vision.pose_estimator import PoseEstimator; from vision.fall_classifier import FallClassifier; from core.state_machine import PostureStateMachine; from core.utils import setup_logger; from sensors.imu_mpu6050 import IMU_MPU6050; from alert.buzzer_led import BuzzerLED; from alert.notifier_line import LineNotifier; from alert.notifier_discord import DiscordNotifier; from storage.db_sqlite import EventDB; from storage.reporter import Reporter; from ui.overlay import Overlay; print('All imports OK')"
```

## Important Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `CAMERA_BACKEND` | `rpicam` | Camera backend |
| `SHOW_WINDOW` | `1` | Show OpenCV window |
| `SIMULATE_GPIO` | `0` | Set `1` to avoid real GPIO output |
| `BUZZER_PWM_ENABLED` | `1` | Use PWM buzzer output |
| `BUZZER_PWM_FREQUENCY` | `2000` | Buzzer PWM frequency |
| `LINE_CHANNEL_ACCESS_TOKEN` | empty | LINE Messaging API token |
| `LINE_TARGET_ID` | empty | LINE user or group id |
| `DISCORD_WEBHOOK_URL` | empty | Discord webhook URL |
| `LOG_FILE_ENABLED` | `1` | Enable file logging |
| `LOG_FILE_PATH` | `data/posture_alarm.log` | Log file or folder path |

## Troubleshooting

If LED works but buzzer does not, use PWM mode:

```bash
python test_bz_led.py --pwm-buzzer --frequency 2000 --duration 2 --repeat 3
```

If LINE works but Discord does not, verify that the webhook starts with:

```text
https://discord.com/api/webhooks/
```

If Python cannot import `requests`:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If GPIO reports `BadPinFactory`, install `python3-lgpio` and reboot.
