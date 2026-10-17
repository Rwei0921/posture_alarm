"""Person presence detection using MediaPipe Pose visibility."""

from __future__ import annotations

from typing import Any

from vision.pose_estimator import PoseEstimator


IMPORTANT_KEYPOINT_INDICES = (0, 11, 12, 23, 24, 25, 26, 27, 28)


class PersonDetector(PoseEstimator):
    def __init__(
        self,
        visibility_threshold: float = 0.5,
        min_visible_keypoints: int = 6,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: str = "models/pose_landmarker_lite.task",
    ) -> None:
        self.visibility_threshold = visibility_threshold
        self.min_visible_keypoints = min_visible_keypoints

        super().__init__(
            model_complexity=0,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_path=model_path,
        )

    def has_person(self, landmarks: list[dict[str, float]]) -> bool:
        visible = sum(1 for lm in landmarks if lm.get("visibility", 0.0) >= self.visibility_threshold)
        if visible < self.min_visible_keypoints:
            return False

        return self._important_visibility_score(landmarks) >= self.visibility_threshold

    @staticmethod
    def _important_visibility_score(landmarks: list[dict[str, float]]) -> float:
        values = [
            landmarks[idx].get("visibility", 0.0)
            for idx in IMPORTANT_KEYPOINT_INDICES
            if idx < len(landmarks)
        ]
        if not values:
            return 0.0
        return float(sum(values) / len(values))

    def detect(self, frame_bgr: Any) -> bool:
        landmarks = self.detect_with_landmarks(frame_bgr)
        return self.has_person(landmarks)

    def detect_with_landmarks(self, frame_bgr: Any) -> list[dict[str, float]]:
        # 共用 Tasks 轉換，維持跌倒分類器需要的 x、y、z、visibility 格式。
        return self.extract_landmarks(frame_bgr)
