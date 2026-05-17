"""Shared utility helpers."""

from __future__ import annotations

import logging
from datetime import datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config


def app_timezone() -> tzinfo:
    try:
        return ZoneInfo(config.APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        fallback = datetime.now().astimezone().tzinfo
        return fallback if fallback is not None else ZoneInfo("UTC")


def now_timestamp() -> str:
    """Return an ISO-8601 timestamp string in the app timezone."""
    return datetime.now(app_timezone()).isoformat(timespec="seconds")


def now_display_timestamp() -> str:
    """Return a human-readable timestamp string in the app timezone."""
    return datetime.now(app_timezone()).strftime("%Y年%m月%d日 %H:%M:%S")


def build_fall_alert_message(timestamp: str | None = None) -> str:
    ts = timestamp or now_display_timestamp()
    return f"姿勢警報：偵測到跌倒，時間：{ts}"


def display_timestamp_from_iso(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp).astimezone(app_timezone()).strftime("%Y年%m月%d日 %H:%M:%S")


def setup_logger(name: str = "posture_alarm", level: int = logging.INFO) -> logging.Logger:
    """Create and configure a consistent console logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    def _converter(seconds: float | None):
        value = seconds if seconds is not None else datetime.now().timestamp()
        return datetime.fromtimestamp(value, tz=app_timezone()).timetuple()

    formatter.converter = _converter

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if config.LOG_FILE_ENABLED:
        log_path = Path(config.LOG_FILE_PATH)
        if not any(isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path for handler in logger.handlers):
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
