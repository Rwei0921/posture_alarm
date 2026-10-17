"""Bounded in-memory camera preview and frame-boundary ROI commands."""

from __future__ import annotations

import base64
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import time
from typing import Any, Callable

from core.roi import apply_roi, roi_from_settings, validate_points


class PreviewStream:
    def __init__(self, settings: Any, send: Callable[[dict[str, Any]], None]) -> None:
        self.settings, self.send = settings, send
        self.lock = Lock()
        self.enabled = False
        self.size = (640, 480)
        self.pending_roi = None
        self.last_frame = float("-inf")
        self.frames: Queue[Any] = Queue(maxsize=1)
        self.closed = Event()
        self.thread = Thread(target=self._encode_loop, daemon=True)
        self.thread.start()

    def command(self, data: dict[str, Any]) -> None:
        if data.get("command") == "preview":
            width = max(64, min(960, int(data.get("width", 640))))
            height = max(64, min(720, int(data.get("height", 480))))
            with self.lock:
                self.enabled = data.get("enabled") is True
                self.size = (width, height)
        elif data.get("command") == "roi":
            points = validate_points(data.get("points"))
            with self.lock:
                self.pending_roi = points
        else:
            raise ValueError("Unknown camera command")

    def apply_pending(self) -> None:
        with self.lock:
            points, self.pending_roi = self.pending_roi, None
        if points is not None:
            active = apply_roi(self.settings, points)
            self.send({"type": "roi_applied", "points": active})

    def offer(self, frame: Any) -> None:
        with self.lock:
            enabled, size = self.enabled, self.size
        now = time.monotonic()
        if not enabled or now - self.last_frame < 1.0 / self.settings.GUI_PREVIEW_FPS:
            return
        self.last_frame = now
        # 複製後才交給編碼執行緒，避免後續 OpenCV 繪圖改到同一張影像。
        item = (frame.copy(), size, roi_from_settings({}, self.settings), now)
        try:
            self.frames.put_nowait(item)
        except Full:
            try:
                self.frames.get_nowait()
            except Empty:
                pass
            try:
                self.frames.put_nowait(item)
            except Full:
                pass

    def _encode_loop(self) -> None:
        while not self.closed.is_set():
            try:
                frame, size, points, captured = self.frames.get(timeout=0.1)
            except Empty:
                continue
            with self.lock:
                enabled = self.enabled
            if not enabled:
                continue
            try:
                import cv2
                height, width = frame.shape[:2]
                ratio = min(1.0, size[0] / width, size[1] / height)
                if ratio < 1:
                    frame = cv2.resize(frame, (max(1, int(width * ratio)), max(1, int(height * ratio))))
                success, encoded = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
                if success:
                    self.send({"type": "frame", "png": base64.b64encode(encoded).decode("ascii"),
                               "points": points, "captured_at": captured})
            except Exception:
                # 預覽失敗不可中止跌倒監控，也不傳送可能含敏感資訊的例外全文。
                self.send({"type": "preview_error"})
                with self.lock:
                    self.enabled = False

    def close(self) -> None:
        self.closed.set()
        self.thread.join(timeout=1.0)
