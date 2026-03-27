"""Rule-based fall classifier from pose landmarks."""

from __future__ import annotations

from collections import deque
import math
import time
from dataclasses import dataclass


@dataclass
class FallFeatures:
    trunk_angle_deg: float
    hip_shoulder_diff: float
    hip_speed: float
    fall_score: float


class FallClassifier:
    def __init__(
        self,
        angle_threshold_deg: float = 55.0,
        hip_shoulder_diff_threshold: float = 0.12,
        speed_threshold: float = 0.28,
        window_size: int = 5,
        score_threshold: float = 0.6,
    ) -> None:
        self.angle_threshold_deg = angle_threshold_deg
        self.hip_shoulder_diff_threshold = hip_shoulder_diff_threshold
        self.speed_threshold = speed_threshold
        self.window_size = max(1, window_size)
        self.score_threshold = max(0.0, min(1.0, score_threshold))
        self._prev_hip_center: tuple[float, float] | None = None
        self._prev_ts: float | None = None
        self._fall_window: deque[bool] = deque(maxlen=self.window_size)

    def classify(
        self, landmarks: list[dict[str, float]], timestamp: float | None = None
    ) -> tuple[bool, FallFeatures]:
        if len(landmarks) < 25:
            self._fall_window.append(False)
            return False, FallFeatures(0.0, 1.0, 0.0, self._current_score())

        now_ts = timestamp if timestamp is not None else time.monotonic()

        shoulder = self._midpoint(landmarks, 11, 12)
        hip = self._midpoint(landmarks, 23, 24)

        trunk_angle = self._trunk_angle_deg(shoulder, hip)
        hip_shoulder_diff = abs(hip[1] - shoulder[1])
        hip_speed = self._hip_speed(hip, now_ts)

        is_fall_posture = (
            trunk_angle >= self.angle_threshold_deg
            and hip_shoulder_diff <= self.hip_shoulder_diff_threshold
        )
        is_rapid_change = hip_speed >= self.speed_threshold and trunk_angle >= (self.angle_threshold_deg * 0.7)
        self._fall_window.append(is_fall_posture or is_rapid_change)
        fall_score = self._current_score()
        return fall_score >= self.score_threshold, FallFeatures(
            trunk_angle,
            hip_shoulder_diff,
            hip_speed,
            fall_score,
        )

    def _current_score(self) -> float:
        if not self._fall_window:
            return 0.0
        return float(sum(self._fall_window) / len(self._fall_window))

    @staticmethod
    def _midpoint(landmarks: list[dict[str, float]], i: int, j: int) -> tuple[float, float]:
        return (
            (landmarks[i]["x"] + landmarks[j]["x"]) / 2.0,
            (landmarks[i]["y"] + landmarks[j]["y"]) / 2.0,
        )

    @staticmethod
    def _trunk_angle_deg(shoulder: tuple[float, float], hip: tuple[float, float]) -> float:
        dx = shoulder[0] - hip[0]
        dy = shoulder[1] - hip[1]
        angle = math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))
        return float(angle)

    def _hip_speed(self, hip_center: tuple[float, float], now_ts: float) -> float:
        if self._prev_hip_center is None or self._prev_ts is None:
            self._prev_hip_center = hip_center
            self._prev_ts = now_ts
            return 0.0

        dt = max(now_ts - self._prev_ts, 1e-6)
        dx = hip_center[0] - self._prev_hip_center[0]
        dy = hip_center[1] - self._prev_hip_center[1]
        speed = math.sqrt(dx * dx + dy * dy) / dt

        self._prev_hip_center = hip_center
        self._prev_ts = now_ts
        return float(speed)
