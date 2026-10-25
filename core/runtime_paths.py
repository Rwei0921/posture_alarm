"""Paths and external-program environment for source and frozen applications."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """模型從封裝資源讀取，不把使用者設定寫進暫存解壓目錄。"""
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def application_root() -> Path:
    """設定與紀錄放在執行檔旁；原始碼模式仍使用專案根目錄。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return resource_root()


def external_program_environment() -> dict[str, str]:
    """rpicam 是系統程式，不應載入 PyInstaller 注入的共用函式庫。"""
    environment = dict(os.environ)
    if is_frozen() and sys.platform.startswith("linux"):
        original = environment.get("LD_LIBRARY_PATH_ORIG")
        if original is None:
            environment.pop("LD_LIBRARY_PATH", None)
        else:
            environment["LD_LIBRARY_PATH"] = original
    return environment
