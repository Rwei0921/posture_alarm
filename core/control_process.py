"""Asynchronous subprocess boundary for the Tkinter control panel."""

from __future__ import annotations

import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import subprocess
import sys
import threading
import time
from typing import Any

from core.control_settings import NOTIFICATION_KEYS, read_env


MESSAGE_PREFIX = "POSTURE_GUI:"


class MonitorProcess:
    """每次只允許一個監控或硬體測試；所有訊息經由有上限的佇列傳回。"""

    def __init__(self, root: Path, env_path: Path) -> None:
        self.root = root
        self.env_path = env_path
        self.messages: Queue[dict[str, Any]] = Queue(maxsize=128)
        self.process: subprocess.Popen[str] | None = None
        self.stopping = False
        self.stop_started = 0.0
        self._reader: threading.Thread | None = None
        self.mode = ""

    @property
    def busy(self) -> bool:
        return self.process is not None

    def start(self, mode: str = "monitor") -> None:
        if self.busy:
            raise RuntimeError("監控或硬體測試尚未停止")
        if mode not in {"monitor", "alarm_test"}:
            raise ValueError("未知的執行模式")
        self.drain()
        environment = dict(os.environ)
        environment.update(read_env(self.env_path))
        environment.update(GUI_ENABLED="0", PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        # 密鑰只透過子程序環境傳入，不放在命令列或 GUI 訊息內。
        self.mode = mode
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(self.root / "control_worker.py"), mode],
            cwd=self.root, env=environment, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.stopping = False
        self._reader = threading.Thread(target=self._read_output, args=(self.process,), daemon=True)
        self._reader.start()

    def _post(self, message: dict[str, Any]) -> None:
        try:
            self.messages.put_nowait(message)
        except Full:
            try:
                self.messages.get_nowait()
            except Empty:
                pass
            try:
                self.messages.put_nowait(message)
            except Full:
                pass

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            if not line.startswith(MESSAGE_PREFIX):
                continue
            try:
                message = json.loads(line[len(MESSAGE_PREFIX):])
            except (ValueError, TypeError):
                continue
            if isinstance(message, dict):
                self._post(message)
        code = process.wait()
        process.stdout.close()
        self._post({"type": "exit", "code": code})

    def stop(self) -> None:
        if not self.process or self.stopping:
            return
        self.stopping = True
        self.stop_started = time.monotonic()
        try:
            assert self.process.stdin is not None
            self.process.stdin.write("stop\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def drain(self) -> list[dict[str, Any]]:
        result = []
        while True:
            try:
                message = self.messages.get_nowait()
            except Empty:
                break
            result.append(message)
            if message.get("type") == "exit":
                if self.process and self.process.stdin:
                    self.process.stdin.close()
                self.process = None
                self.stopping = False
        return result


def test_notification(channel: str, values: dict[str, str]) -> bool:
    """沿用原有通知邊界；呼叫端必須先取得使用者的測試確認。"""
    if channel == "line":
        from alert.notifier_line import LineNotifier
        sender = LineNotifier(values[NOTIFICATION_KEYS[0]], values[NOTIFICATION_KEYS[1]])
    elif channel == "discord":
        from alert.notifier_discord import DiscordNotifier
        sender = DiscordNotifier(values[NOTIFICATION_KEYS[2]])
    else:
        raise ValueError("未知的通知管道")
    return sender.send("Posture Alarm GUI test notification")
