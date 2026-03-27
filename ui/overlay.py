"""Frame overlay rendering helpers."""

from __future__ import annotations

import importlib
from typing import Any


class Overlay:
    def __init__(self, font_scale: float = 0.7, thickness: int = 2) -> None:
        self.font_scale = font_scale
        self.thickness = thickness

    @staticmethod
    def _load_cv2() -> Any:
        try:
            return importlib.import_module("cv2")
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("OpenCV is required for Overlay") from exc

    def draw_status(self, frame: Any, state_text: str, warning: bool = False) -> Any:
        cv2 = self._load_cv2()
        color = (0, 0, 255) if warning else (0, 200, 0)
        cv2.putText(
            frame,
            f"State: {state_text}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_scale,
            color,
            self.thickness,
            cv2.LINE_AA,
        )
        return frame

    def draw_alert(self, frame: Any, message: str) -> Any:
        cv2 = self._load_cv2()
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (10, h - 70), (w - 10, h - 20), (0, 0, 255), 2)
        cv2.putText(
            frame,
            message,
            (20, h - 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_scale,
            (0, 0, 255),
            self.thickness,
            cv2.LINE_AA,
        )
        return frame

    def draw_landmarks(self, frame: Any, landmarks: list[dict[str, float]]) -> Any:
        cv2 = self._load_cv2()
        h, w = frame.shape[:2]
        for lm in landmarks:
            if lm.get("visibility", 0.0) < 0.3:
                continue
            x = int(lm["x"] * w)
            y = int(lm["y"] * h)
            cv2.circle(frame, (x, y), 3, (255, 180, 0), -1)
        return frame

    def draw_bed_roi(
        self,
        frame: Any,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        label: str = "BED ROI",
    ) -> Any:
        cv2 = self._load_cv2()
        h, w = frame.shape[:2]
        p1 = (int(max(0.0, min(1.0, x1)) * w), int(max(0.0, min(1.0, y1)) * h))
        p2 = (int(max(0.0, min(1.0, x2)) * w), int(max(0.0, min(1.0, y2)) * h))
        cv2.rectangle(frame, p1, p2, (0, 170, 255), 2)
        cv2.putText(
            frame,
            label,
            (p1[0], max(20, p1[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_scale * 0.8,
            (0, 170, 255),
            max(1, self.thickness - 1),
            cv2.LINE_AA,
        )
        return frame

    def draw_bed_polygon(
        self,
        frame: Any,
        points: list[tuple[float, float]],
        label: str = "BED ROI",
    ) -> Any:
        if len(points) < 3:
            return frame
        cv2 = self._load_cv2()
        np = importlib.import_module("numpy")
        h, w = frame.shape[:2]
        pixel_points = [
            (
                int(max(0.0, min(1.0, x)) * w),
                int(max(0.0, min(1.0, y)) * h),
            )
            for x, y in points
        ]
        poly = np.array(pixel_points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [poly], True, (0, 170, 255), 2)
        for p in pixel_points:
            cv2.circle(frame, p, 4, (0, 170, 255), -1)
        cv2.putText(
            frame,
            label,
            (pixel_points[0][0], max(20, pixel_points[0][1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_scale * 0.8,
            (0, 170, 255),
            max(1, self.thickness - 1),
            cv2.LINE_AA,
        )
        return frame
