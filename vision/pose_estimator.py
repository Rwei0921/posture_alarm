"""MediaPipe Tasks PoseLandmarker keypoint extraction."""

from __future__ import annotations

import importlib
from pathlib import Path
import time
from typing import Any


class PoseEstimator:
    def __init__(
        self,
        static_image_mode: bool = False,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: str = "models/pose_landmarker_lite.task",
    ) -> None:
        path = Path(model_path).expanduser()
        # 相對路徑以專案根目錄為準，避免從其他目錄啟動時找不到模型。
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        if not path.is_file():
            raise FileNotFoundError(f"Pose model not found: {path}. Set POSE_MODEL_PATH to a .task model.")
        self._mp = self._load_mediapipe()
        self._static_image_mode = static_image_mode
        self._last_timestamp_ms = -1
        vision = self._mp.tasks.vision
        # 保留 model_complexity 參數相容舊呼叫；Tasks 的模型種類由模型檔決定。
        options = vision.PoseLandmarkerOptions(
            base_options=self._mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE if static_image_mode else vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._pose = vision.PoseLandmarker.create_from_options(options)

    @staticmethod
    def _load_mediapipe() -> Any:
        try:
            return importlib.import_module("mediapipe")
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("mediapipe is required for PoseEstimator") from exc

    def extract_landmarks(self, frame_bgr: Any) -> list[dict[str, float]]:
        cv2 = self._load_cv2()
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=frame_rgb)
        if self._static_image_mode:
            results = self._pose.detect(image)
        else:
            # Tasks 影片模式要求時間戳嚴格遞增，即使連續呼叫落在同一毫秒。
            timestamp_ms = max(time.monotonic_ns() // 1_000_000, self._last_timestamp_ms + 1)
            self._last_timestamp_ms = timestamp_ms
            results = self._pose.detect_for_video(image, timestamp_ms)

        if not results.pose_landmarks:
            return []

        landmarks: list[dict[str, float]] = []
        for lm in results.pose_landmarks[0]:
            landmarks.append(
                {
                    "x": float(lm.x),
                    "y": float(lm.y),
                    "z": float(lm.z),
                    "visibility": float(lm.visibility) if lm.visibility is not None else 0.0,
                }
            )
        return landmarks

    def close(self) -> None:
        self._pose.close()

    @staticmethod
    def _load_cv2() -> Any:
        try:
            return importlib.import_module("cv2")
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("OpenCV is required for PoseEstimator") from exc
