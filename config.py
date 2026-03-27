"""Global configuration for posture alarm pipeline."""

from __future__ import annotations

import os
from pathlib import Path

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

# MediaPipe / pose
MP_STATIC_IMAGE_MODE = False
MP_MODEL_COMPLEXITY = int(os.getenv("MP_MODEL_COMPLEXITY", "1"))
MP_MIN_DETECTION_CONFIDENCE = float(os.getenv("MP_MIN_DETECTION_CONFIDENCE", "0.5"))
MP_MIN_TRACKING_CONFIDENCE = float(os.getenv("MP_MIN_TRACKING_CONFIDENCE", "0.5"))
POSE_VISIBILITY_THRESHOLD = float(os.getenv("POSE_VISIBILITY_THRESHOLD", "0.5"))
MIN_VISIBLE_KEYPOINTS = int(os.getenv("MIN_VISIBLE_KEYPOINTS", "6"))

# Fall detection thresholds
FALL_TRUNK_ANGLE_THRESHOLD_DEG = float(os.getenv("FALL_TRUNK_ANGLE_THRESHOLD_DEG", "55.0"))
FALL_HIP_SHOULDER_DIFF_THRESHOLD = float(os.getenv("FALL_HIP_SHOULDER_DIFF_THRESHOLD", "0.12"))
FALL_SPEED_THRESHOLD = float(os.getenv("FALL_SPEED_THRESHOLD", "0.28"))
FALL_SCORE_WINDOW_SIZE = int(os.getenv("FALL_SCORE_WINDOW_SIZE", "5"))
FALL_SCORE_THRESHOLD = float(os.getenv("FALL_SCORE_THRESHOLD", "0.6"))
FALL_EVENT_MIN_HIP_DROP = float(os.getenv("FALL_EVENT_MIN_HIP_DROP", "0.12"))
FALL_EVENT_WINDOW_SECONDS = float(os.getenv("FALL_EVENT_WINDOW_SECONDS", "1.5"))

# Bed region-of-interest (normalized 0~1) for false-positive reduction
BED_ROI_ENABLED = os.getenv("BED_ROI_ENABLED", "0") == "1"
BED_ROI_X1 = float(os.getenv("BED_ROI_X1", "0.20"))
BED_ROI_Y1 = float(os.getenv("BED_ROI_Y1", "0.35"))
BED_ROI_X2 = float(os.getenv("BED_ROI_X2", "0.90"))
BED_ROI_Y2 = float(os.getenv("BED_ROI_Y2", "0.95"))
BED_ROI_SHOW = os.getenv("BED_ROI_SHOW", "1") == "1"
BED_ROI_MARK_ON_START = os.getenv("BED_ROI_MARK_ON_START", "1") == "1"
BED_ROI_MARK_SCALE = float(os.getenv("BED_ROI_MARK_SCALE", "0.5"))

# State machine timing (seconds)
SUSPECT_FALL_TIMEOUT = float(os.getenv("SUSPECT_FALL_TIMEOUT", "2.0"))
FALL_CONFIRM_SECONDS = float(os.getenv("FALL_CONFIRM_SECONDS", "1.2"))
SEDENTARY_SECONDS = float(os.getenv("SEDENTARY_SECONDS", "1800"))
FALL_RECOVERY_SECONDS = float(os.getenv("FALL_RECOVERY_SECONDS", "5.0"))

# Sensors
SIMULATE_IMU = os.getenv("SIMULATE_IMU", "1") == "1"
IMU_SHOCK_THRESHOLD_G = float(os.getenv("IMU_SHOCK_THRESHOLD_G", "1.8"))

# Alert
SIMULATE_GPIO = os.getenv("SIMULATE_GPIO", "1") == "1"
ALERT_ON_FALL_ONLY = os.getenv("ALERT_ON_FALL_ONLY", "1") == "1"
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "60"))

# Notifier
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Storage
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
DB_PATH = str(DATA_DIR / "events.db")
