"""Global configuration for posture alarm pipeline."""

from __future__ import annotations

import os
from pathlib import Path

# Timezone
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Taipei")

# Camera
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
CAMERA_BACKEND = os.getenv("CAMERA_BACKEND", "rpicam")
CAMERA_WARMUP_FRAMES = int(os.getenv("CAMERA_WARMUP_FRAMES", "10"))
CAMERA_READ_RETRY = int(os.getenv("CAMERA_READ_RETRY", "3"))
CAMERA_MAX_READ_FAILURES = int(os.getenv("CAMERA_MAX_READ_FAILURES", "60"))
RPICAM_FPS = int(os.getenv("RPICAM_FPS", "15"))
RPICAM_TIMEOUT_MS = int(os.getenv("RPICAM_TIMEOUT_MS", "800"))
RPICAM_BUFFER_MAX_BYTES = int(os.getenv("RPICAM_BUFFER_MAX_BYTES", str(4 * 1024 * 1024)))
SHOW_WINDOW = os.getenv("SHOW_WINDOW", "1") == "1"
DISPLAY_SCALE = float(os.getenv("DISPLAY_SCALE", "0.5"))

# 控制面板預設關閉，保留原本 CLI 啟動方式。
GUI_ENABLED = os.getenv("GUI_ENABLED", "0") == "1"
GUI_REFRESH_MS = max(100, min(5000, int(os.getenv("GUI_REFRESH_MS", "500"))))

# PCB hardware pins and environment sensors
BUZZER_GPIO_PIN = int(os.getenv("BUZZER_GPIO_PIN", "17"))
LED_GPIO_PIN = int(os.getenv("LED_GPIO_PIN", "18"))
LED_2_GPIO_PIN = int(os.getenv("LED_2_GPIO_PIN", "22"))
LED_2_ENABLED = os.getenv("LED_2_ENABLED", "1") == "1"
DHT22_ENABLED = os.getenv("DHT22_ENABLED", "1") == "1"
DHT22_DATA_PIN = int(os.getenv("DHT22_DATA_PIN", "4"))
DHT22_USE_PULSEIO = os.getenv("DHT22_USE_PULSEIO", "0") == "1"
DHT22_READ_INTERVAL_SECONDS = float(os.getenv("DHT22_READ_INTERVAL_SECONDS", "2.0"))
DHT22_LOG_INTERVAL_SECONDS = float(os.getenv("DHT22_LOG_INTERVAL_SECONDS", "60.0"))
DHT22_SHOW = os.getenv("DHT22_SHOW", "1") == "1"

# SHT31 is the PCB default; select dht22 for the legacy sensor only.
ENV_SENSOR_BACKEND = os.getenv("ENV_SENSOR_BACKEND", "sht31").lower()
SHT31_I2C_BUS = int(os.getenv("SHT31_I2C_BUS", "1"))
SHT31_I2C_ADDRESS = int(os.getenv("SHT31_I2C_ADDRESS", "0x44"), 0)
DHT22_FALLBACK_ENABLED = os.getenv("DHT22_FALLBACK_ENABLED", "0") == "1"
ENV_READ_INTERVAL_SECONDS = float(os.getenv("ENV_READ_INTERVAL_SECONDS", str(DHT22_READ_INTERVAL_SECONDS)))
ENV_LOG_INTERVAL_SECONDS = float(os.getenv("ENV_LOG_INTERVAL_SECONDS", str(DHT22_LOG_INTERVAL_SECONDS)))
ENV_SHOW = os.getenv("ENV_SHOW", "1" if DHT22_SHOW else "0") == "1"

# MediaPipe / pose
# Tasks 姿態模型路徑，可透過環境變數指定其他 .task 檔案。
POSE_MODEL_PATH = os.getenv("POSE_MODEL_PATH", "models/pose_landmarker_lite.task")
MP_STATIC_IMAGE_MODE = False
MP_MODEL_COMPLEXITY = int(os.getenv("MP_MODEL_COMPLEXITY", "1"))
MP_MIN_DETECTION_CONFIDENCE = float(os.getenv("MP_MIN_DETECTION_CONFIDENCE", "0.5"))
MP_MIN_TRACKING_CONFIDENCE = float(os.getenv("MP_MIN_TRACKING_CONFIDENCE", "0.5"))
POSE_VISIBILITY_THRESHOLD = float(os.getenv("POSE_VISIBILITY_THRESHOLD", "0.6"))
MIN_VISIBLE_KEYPOINTS = int(os.getenv("MIN_VISIBLE_KEYPOINTS", "10"))

# Fall detection thresholds
FALL_TRUNK_ANGLE_THRESHOLD_DEG = float(os.getenv("FALL_TRUNK_ANGLE_THRESHOLD_DEG", "55.0"))
FALL_HIP_SHOULDER_DIFF_THRESHOLD = float(os.getenv("FALL_HIP_SHOULDER_DIFF_THRESHOLD", "0.12"))
FALL_SPEED_THRESHOLD = float(os.getenv("FALL_SPEED_THRESHOLD", "0.25"))
FALL_SCORE_WINDOW_SIZE = int(os.getenv("FALL_SCORE_WINDOW_SIZE", "5"))
FALL_SCORE_THRESHOLD = float(os.getenv("FALL_SCORE_THRESHOLD", "0.70"))
FALL_EVENT_MIN_HIP_DROP = float(os.getenv("FALL_EVENT_MIN_HIP_DROP", "0.12"))
FALL_EVENT_WINDOW_SECONDS = float(os.getenv("FALL_EVENT_WINDOW_SECONDS", "1.0"))

# Bed region-of-interest (normalized 0~1) for false-positive reduction
BED_ROI_ENABLED = os.getenv("BED_ROI_ENABLED", "0") == "1"
BED_ROI_X1 = float(os.getenv("BED_ROI_X1", "0.20"))
BED_ROI_Y1 = float(os.getenv("BED_ROI_Y1", "0.35"))
BED_ROI_X2 = float(os.getenv("BED_ROI_X2", "0.90"))
BED_ROI_Y2 = float(os.getenv("BED_ROI_Y2", "0.95"))
BED_ROI_SHOW = os.getenv("BED_ROI_SHOW", "1") == "1"
BED_ROI_MARK_ON_START = os.getenv("BED_ROI_MARK_ON_START", "1") == "1"
BED_ROI_MARK_SCALE = float(os.getenv("BED_ROI_MARK_SCALE", "0.5"))
BED_POLYGON_ENABLED = os.getenv("BED_POLYGON_ENABLED", "0") == "1"
BED_POLY_P1_X = float(os.getenv("BED_POLY_P1_X", "0.20"))
BED_POLY_P1_Y = float(os.getenv("BED_POLY_P1_Y", "0.35"))
BED_POLY_P2_X = float(os.getenv("BED_POLY_P2_X", "0.90"))
BED_POLY_P2_Y = float(os.getenv("BED_POLY_P2_Y", "0.35"))
BED_POLY_P3_X = float(os.getenv("BED_POLY_P3_X", "0.90"))
BED_POLY_P3_Y = float(os.getenv("BED_POLY_P3_Y", "0.95"))
BED_POLY_P4_X = float(os.getenv("BED_POLY_P4_X", "0.20"))
BED_POLY_P4_Y = float(os.getenv("BED_POLY_P4_Y", "0.95"))

# State machine timing (seconds)
SUSPECT_FALL_TIMEOUT = float(os.getenv("SUSPECT_FALL_TIMEOUT", "2.0"))
FALL_CONFIRM_SECONDS = float(os.getenv("FALL_CONFIRM_SECONDS", "1.2"))
# Keep the event gate open through confirmation (see TUNING_GUIDE.md).
FALL_EVENT_WINDOW_SECONDS = max(FALL_EVENT_WINDOW_SECONDS, FALL_CONFIRM_SECONDS)
SEDENTARY_SECONDS = float(os.getenv("SEDENTARY_SECONDS", "1800"))
FALL_RECOVERY_SECONDS = float(os.getenv("FALL_RECOVERY_SECONDS", "5.0"))

# Alert
SIMULATE_GPIO = os.getenv("SIMULATE_GPIO", "0") == "1"
BUZZER_PWM_ENABLED = os.getenv("BUZZER_PWM_ENABLED", "1") == "1"
BUZZER_PWM_FREQUENCY = float(os.getenv("BUZZER_PWM_FREQUENCY", "2000"))
ALERT_ON_FALL_ONLY = os.getenv("ALERT_ON_FALL_ONLY", "1") == "1"
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "60"))

# Logging
LOG_FILE_ENABLED = os.getenv("LOG_FILE_ENABLED", "1") == "1"
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", str(Path(__file__).resolve().parent / "data" / "posture_alarm.log"))

# Notifier
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_TARGET_ID = os.getenv("LINE_TARGET_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Storage
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
DB_PATH = str(DATA_DIR / "events.db")
