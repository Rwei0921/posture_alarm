"""Validated control-panel settings and private, atomic env-file updates."""

from __future__ import annotations

import math
import os
from pathlib import Path
import re
import shlex
import tempfile
from dataclasses import dataclass
from urllib.parse import urlparse


NOTIFICATION_KEYS = ("LINE_CHANNEL_ACCESS_TOKEN", "LINE_TARGET_ID", "DISCORD_WEBHOOK_URL")
SECRET_MASK = "*"


@dataclass(frozen=True)
class ThresholdSpec:
    key: str
    label: str
    default: float | int
    minimum: float
    maximum: float
    hint: str
    integer: bool = False


THRESHOLDS = (
    ThresholdSpec("FALL_TRUNK_ANGLE_THRESHOLD_DEG", "身體角度門檻（度）", 55.0, 1, 90, "調低較敏感；仍須符合原有事件條件"),
    ThresholdSpec("FALL_HIP_SHOULDER_DIFF_THRESHOLD", "髖肩高度差（畫面比例）", 0.12, 0.001, 1, "調高允許較大的肩髖高度差"),
    ThresholdSpec("FALL_SPEED_THRESHOLD", "髖部速度（畫面比例／秒）", 0.25, 0.001, 10, "調低可接受較慢的移動；仍有角度條件"),
    ThresholdSpec("FALL_SCORE_WINDOW_SIZE", "平滑視窗（幀）", 5, 1, 120, "較小反應較快，但結果可能較不穩定", integer=True),
    ThresholdSpec("FALL_SCORE_THRESHOLD", "跌倒分數門檻（0～1）", 0.70, 0.01, 1, "調低較容易達到跌倒分數"),
    ThresholdSpec("FALL_EVENT_MIN_HIP_DROP", "單幀髖部下降（畫面比例）", 0.12, 0.001, 1, "調低可接受較小的單幀下降；不是累積距離"),
    ThresholdSpec("FALL_EVENT_WINDOW_SECONDS", "事件保留時間（秒）", 1.2, 0.1, 60, "須不少於確認時間；延長可保留先前跌倒事件"),
    ThresholdSpec("FALL_CONFIRM_SECONDS", "跌倒確認時間（秒）", 1.2, 0.1, 30, "縮短可較快確認，但可能增加誤報"),
    ThresholdSpec("SUSPECT_FALL_TIMEOUT", "疑似狀態逾時（秒）", 2.0, 0.1, 60, "沒有持續達標時，等待多久回到正常"),
    ThresholdSpec("FALL_RECOVERY_SECONDS", "恢復等待時間（秒）", 5.0, 0.1, 300, "連續非跌倒才解除；不影響觸發敏感度"),
)
BALANCED_PRESET = {spec.key: str(spec.default) for spec in THRESHOLDS}
SENSITIVE_PRESET = dict(zip((spec.key for spec in THRESHOLDS), (
    "48.0", "0.16", "0.20", "5", "0.55", "0.09", "1.8", "1.0", "3.0", "5.0",
)))
EDITABLE_KEYS = set(BALANCED_PRESET) | set(NOTIFICATION_KEYS) | {"GUI_ENABLED", "GUI_REFRESH_MS"}
_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def parse_env(text: str) -> dict[str, str]:
    """只讀取純量設定，絕不執行 shell 指令或展開環境變數。"""
    values = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _ASSIGNMENT.match(line)
        if match is None:
            raise ValueError(f"設定檔第 {number} 行格式不支援，請使用 KEY=value")
        try:
            tokens = shlex.split(match[2], comments=True, posix=True)
        except ValueError:
            raise ValueError(f"設定檔第 {number} 行引號不完整") from None
        if len(tokens) > 1:
            raise ValueError(f"設定檔第 {number} 行含空白的值必須加引號")
        values[match[1]] = tokens[0] if tokens else ""
    return values


def read_env(path: Path) -> dict[str, str]:
    return parse_env(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def validate_thresholds(values: dict[str, str]) -> dict[str, str]:
    result = {}
    for spec in THRESHOLDS:
        try:
            value = float(values[spec.key])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{spec.label}：請輸入數字") from None
        if not math.isfinite(value) or not spec.minimum <= value <= spec.maximum:
            raise ValueError(f"{spec.label}：範圍為 {spec.minimum:g}～{spec.maximum:g}")
        if spec.integer and not value.is_integer():
            raise ValueError(f"{spec.label}：必須是整數")
        result[spec.key] = str(int(value)) if spec.integer else str(value)
    confirm = float(result["FALL_CONFIRM_SECONDS"])
    if float(result["FALL_EVENT_WINDOW_SECONDS"]) < confirm:
        raise ValueError("事件保留時間必須不少於跌倒確認時間")
    if float(result["SUSPECT_FALL_TIMEOUT"]) < confirm:
        raise ValueError("疑似狀態逾時必須不少於跌倒確認時間")
    return result


def validate_notifications(values: dict[str, str]) -> dict[str, str]:
    result = {key: values.get(key, "").strip() for key in NOTIFICATION_KEYS}
    if any("\n" in value or "\r" in value or "\x00" in value for value in result.values()):
        raise ValueError("通知設定不能包含換行或控制字元")
    url = result["DISCORD_WEBHOOK_URL"]
    if url:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname not in {"discord.com", "discordapp.com"}
                or not re.fullmatch(r"/api(?:/v\d+)?/webhooks/[^/]+/[^/]+", parsed.path)
                or parsed.username or parsed.password or parsed.fragment):
            raise ValueError("Discord 請填入有效的 HTTPS Webhook URL")
    return result


def update_env(path: Path, updates: dict[str, str], expected: dict[str, str] | None = None) -> None:
    """保留其他設定，安全引用特殊字元，並在同目錄原子替換。"""
    if not set(updates) <= EDITABLE_KEYS:
        raise ValueError("控制面板只能儲存通知與閾值設定")
    if any(any(char in value for char in "\r\n\x00") for value in updates.values()):
        raise ValueError("設定值不能包含換行或控制字元")
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    current = parse_env(text)
    if expected is not None and any(current.get(key) != expected.get(key) for key in updates):
        raise ValueError("設定已被其他程式修改，請先重新載入再儲存")
    newline = "\n"
    lines, written = [], set()
    for line in text.splitlines(keepends=True):
        match = _ASSIGNMENT.match(line.rstrip("\r\n"))
        key = match[1] if match else None
        if key in updates:
            if key not in written:
                lines.append(f"{key}={shlex.quote(updates[key])}{newline}")
                written.add(key)
        else:
            lines.append(line)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += newline
    lines.extend(f"{key}={shlex.quote(value)}{newline}" for key, value in updates.items() if key not in written)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".env-update-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.writelines(lines)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "posix":
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
