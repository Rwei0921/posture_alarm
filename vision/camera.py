"""Camera adapter supporting OpenCV and Picamera2 backends."""

from __future__ import annotations

import importlib
import os
import select
import signal
import subprocess
import time
from typing import Any, Tuple

from core.runtime_paths import external_program_environment


class Camera:
    def __init__(
        self,
        source: int | str = 0,
        width: int | None = None,
        height: int | None = None,
        backend: str = "auto",
        warmup_frames: int = 10,
        read_retry: int = 3,
        rpicam_fps: int = 15,
        rpicam_timeout_ms: int = 800,
        rpicam_buffer_max_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self.source = int(source) if isinstance(source, str) and source.isdigit() else source
        self.width = width
        self.height = height
        self.backend = backend.lower()
        self.warmup_frames = max(0, warmup_frames)
        self.read_retry = max(1, read_retry)
        self.rpicam_fps = max(1, rpicam_fps)
        self.rpicam_timeout_ms = max(50, rpicam_timeout_ms)
        self.rpicam_buffer_max_bytes = max(512 * 1024, rpicam_buffer_max_bytes)

        self._cv2 = None
        self.cap = None
        self._picamera2 = None
        self._rpicam_proc: subprocess.Popen[bytes] | None = None
        self._rpicam_buffer = bytearray()
        self._rpicam_restarts = 0
        self._using_backend = ""

        if self.backend not in {"auto", "opencv", "picamera2", "rpicam"}:
            raise ValueError("backend must be one of: auto, opencv, picamera2, rpicam")

        if self.backend == "picamera2":
            self._open_picamera2(strict=True)
        elif self.backend == "rpicam":
            self._open_rpicam(strict=True)
        elif self.backend == "opencv":
            self._open_opencv(strict=True)
        else:
            # auto mode: prefer picamera2 (best for Raspberry Pi Camera Module 3), then fallback to OpenCV.
            if not self._open_picamera2(strict=False):
                if not self._open_rpicam(strict=False):
                    self._open_opencv(strict=True)

        if self._using_backend == "opencv":
            self._warmup_opencv()

    def _infer_flat_shape(self, flat_size: int) -> tuple[int, int] | None:
        if flat_size <= 0 or (flat_size % 3) != 0:
            return None

        pixels = flat_size // 3
        candidates: list[tuple[int, int]] = []

        if self.width and self.height:
            candidates.append((self.width, self.height))

        if self.cap is not None and self._cv2 is not None:
            try:
                cap_w = int(self.cap.get(self._cv2.CAP_PROP_FRAME_WIDTH))
                cap_h = int(self.cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT))
                if cap_w > 0 and cap_h > 0:
                    candidates.append((cap_w, cap_h))
            except Exception:
                pass

        candidates.extend(
            [
                (640, 480),
                (1280, 720),
                (1920, 1080),
                (320, 240),
                (800, 600),
            ]
        )

        for w, h in candidates:
            if w * h == pixels:
                return w, h

        return None

    @staticmethod
    def _load_cv2():
        try:
            return importlib.import_module("cv2")
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("OpenCV is required for Camera") from exc

    @staticmethod
    def _load_picamera2() -> Any:
        try:
            return getattr(importlib.import_module("picamera2"), "Picamera2")
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("picamera2 is required for Camera backend 'picamera2'") from exc

    def _open_opencv(self, strict: bool) -> bool:
        try:
            self._cv2 = self._load_cv2()
            cap = self._cv2.VideoCapture(self.source)

            if self.width is not None:
                cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, self.width)
            if self.height is not None:
                cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            if not cap.isOpened():
                cap.release()
                if strict:
                    raise RuntimeError(f"Cannot open OpenCV camera source: {self.source}")
                return False

            self.cap = cap
            self._using_backend = "opencv"
            return True
        except Exception:
            if strict:
                raise
            return False

    def _open_picamera2(self, strict: bool) -> bool:
        try:
            Picamera2 = self._load_picamera2()
            picam2 = Picamera2()
            main_cfg: dict[str, Any] = {}
            if self.width is not None and self.height is not None:
                main_cfg["size"] = (self.width, self.height)

            config = picam2.create_preview_configuration(main=main_cfg or None)
            picam2.configure(config)
            picam2.start()

            self._picamera2 = picam2
            self._using_backend = "picamera2"
            return True
        except Exception:
            if strict:
                raise
            return False

    def _open_rpicam(self, strict: bool) -> bool:
        try:
            width = self.width if self.width is not None else 640
            height = self.height if self.height is not None else 480

            cmd = [
                "rpicam-vid",
                "-t",
                "0",
                "--codec",
                "mjpeg",
                "--inline",
                "--flush",
                "--nopreview",
                "--width",
                str(width),
                "--height",
                str(height),
                "--framerate",
                str(self.rpicam_fps),
                "-o",
                "-",
            ]

            self._rpicam_proc = subprocess.Popen(
                cmd,
                env=external_program_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
                start_new_session=(os.name != "nt"),
            )
            self._rpicam_buffer.clear()
            self._using_backend = "rpicam"
            return True
        except Exception:
            if strict:
                raise
            return False

    def _restart_rpicam(self) -> bool:
        if self._rpicam_proc is not None:
            try:
                if self._rpicam_proc.poll() is None:
                    self._rpicam_proc.terminate()
                    self._rpicam_proc.wait(timeout=0.5)
            except Exception:
                pass
        self._rpicam_proc = None
        self._rpicam_restarts += 1
        return self._open_rpicam(strict=False)

    def is_opened(self) -> bool:
        if self._using_backend == "picamera2":
            return self._picamera2 is not None
        if self._using_backend == "rpicam":
            return self._rpicam_proc is not None and self._rpicam_proc.poll() is None
        return bool(self.cap and self.cap.isOpened())

    def _warmup_opencv(self) -> None:
        if self.cap is None:
            return
        for _ in range(self.warmup_frames):
            try:
                self.cap.read()
            except Exception:
                break
            time.sleep(0.02)

    def _read_rpicam_chunk(self) -> bytes:
        if self._rpicam_proc is None or self._rpicam_proc.stdout is None:
            return b""

        stream = self._rpicam_proc.stdout

        if os.name != "nt":
            try:
                ready, _, _ = select.select([stream], [], [], 0.05)
                if not ready:
                    return b""
            except Exception:
                return b""

        try:
            read1 = getattr(stream, "read1", None)
            if callable(read1):
                chunk = read1(65536)
            else:
                chunk = stream.read(65536)
            if isinstance(chunk, bytes):
                return chunk
            return b""
        except Exception:
            return b""

    def _read_rpicam_frame(self) -> Tuple[bool, Any]:
        if self._rpicam_proc is None or self._rpicam_proc.poll() is not None:
            if self._rpicam_restarts < 2 and self._restart_rpicam():
                pass
            else:
                return False, None

        if self._rpicam_proc is None or self._rpicam_proc.poll() is not None:
            return False, None

        cv2 = self._load_cv2()
        np = importlib.import_module("numpy")

        deadline = time.monotonic() + (self.rpicam_timeout_ms / 1000.0)

        while time.monotonic() < deadline:
            chunk = self._read_rpicam_chunk()
            if chunk:
                self._rpicam_buffer.extend(chunk)
                if len(self._rpicam_buffer) > self.rpicam_buffer_max_bytes:
                    overflow = len(self._rpicam_buffer) - self.rpicam_buffer_max_bytes
                    del self._rpicam_buffer[:overflow]

            start = self._rpicam_buffer.find(b"\xff\xd8")
            if start < 0:
                continue

            end = self._rpicam_buffer.find(b"\xff\xd9", start + 2)
            if end < 0:
                continue

            jpeg_bytes = bytes(self._rpicam_buffer[start : end + 2])
            del self._rpicam_buffer[: end + 2]

            frame = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                return True, frame

        return False, None

    def _normalize_frame(self, frame: Any) -> Any | None:
        if frame is None:
            return None

        if hasattr(frame, "shape"):
            shape = frame.shape
            if len(shape) == 2 and shape[0] == 1:
                flat_size = int(shape[1])
                inferred = self._infer_flat_shape(flat_size)
                if inferred is not None:
                    try:
                        w, h = inferred
                        reshaped = frame.reshape((h, w, 3))
                        return reshaped[:, :, ::-1]
                    except Exception:
                        return None
                return None
            if len(shape) == 3 and shape[2] == 3:
                return frame
            if len(shape) == 3 and shape[2] == 4:
                return frame[:, :, :3]

        return None

    def read_frame(self) -> Tuple[bool, Any]:
        if not self.is_opened():
            return False, None

        if self._using_backend == "picamera2":
            if self._picamera2 is None:
                return False, None
            frame = self._picamera2.capture_array()
            # Picamera2 often returns XBGR8888/RGBA; normalize to 3-channel BGR.
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = frame[:, :, :3]
            frame_bgr = frame[..., ::-1].copy()
            return True, frame_bgr

        if self._using_backend == "rpicam":
            return self._read_rpicam_frame()

        if self.cap is None:
            return False, None
        for _ in range(self.read_retry):
            try:
                ok, frame = self.cap.read()
            except Exception:
                ok, frame = False, None
            normalized = self._normalize_frame(frame) if ok else None
            if ok and normalized is not None:
                return True, normalized
            time.sleep(0.01)
        return False, None

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self._picamera2 is not None:
            try:
                self._picamera2.stop()
            finally:
                self._picamera2.close()
                self._picamera2 = None
        if self._rpicam_proc is not None:
            try:
                if self._rpicam_proc.poll() is None:
                    if os.name != "nt":
                        os.killpg(self._rpicam_proc.pid, signal.SIGTERM)
                    else:
                        self._rpicam_proc.terminate()
                    self._rpicam_proc.wait(timeout=1.5)
            except Exception:
                if self._rpicam_proc.poll() is None:
                    if os.name != "nt":
                        os.killpg(self._rpicam_proc.pid, signal.SIGKILL)
                    else:
                        self._rpicam_proc.kill()
            finally:
                self._rpicam_proc = None
                self._rpicam_buffer.clear()
