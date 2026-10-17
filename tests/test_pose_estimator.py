"""Hardware-free coverage of the MediaPipe Tasks compatibility boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import config
from vision.person_detector import PersonDetector
from vision.pose_estimator import PoseEstimator


@pytest.fixture
def tasks(monkeypatch):
    pose = Mock()
    pose.detect.return_value = SimpleNamespace(pose_landmarks=[])
    pose.detect_for_video.return_value = SimpleNamespace(pose_landmarks=[])
    vision = SimpleNamespace(
        RunningMode=SimpleNamespace(IMAGE="image", VIDEO="video"),
        PoseLandmarkerOptions=Mock(side_effect=lambda **kw: SimpleNamespace(**kw)),
        PoseLandmarker=SimpleNamespace(create_from_options=Mock(return_value=pose)),
    )
    mp = SimpleNamespace(
        tasks=SimpleNamespace(vision=vision, BaseOptions=Mock(side_effect=lambda **kw: SimpleNamespace(**kw))),
        Image=Mock(), ImageFormat=SimpleNamespace(SRGB="srgb"),
    )
    cv2 = SimpleNamespace(cvtColor=Mock(return_value="rgb"), COLOR_BGR2RGB=1)
    monkeypatch.setattr(PoseEstimator, "_load_mediapipe", staticmethod(lambda: mp))
    monkeypatch.setattr(PoseEstimator, "_load_cv2", staticmethod(lambda: cv2))
    return mp, vision, pose, cv2


@pytest.mark.parametrize("cls", [PoseEstimator, PersonDetector])
def test_video_options_and_strict_timestamps(tasks, monkeypatch, tmp_path, cls):
    mp, vision, pose, cv2 = tasks
    model = tmp_path / "custom.task"
    model.touch()
    estimator = cls(min_detection_confidence=0.7, min_tracking_confidence=0.8, model_path=str(model))
    options = vision.PoseLandmarker.create_from_options.call_args.args[0]
    assert options.base_options.model_asset_path == str(model)
    assert options.running_mode == "video"
    assert options.num_poses == 1
    assert options.min_pose_detection_confidence == 0.7
    assert options.min_pose_presence_confidence == 0.7
    assert options.min_tracking_confidence == 0.8
    monkeypatch.setattr("vision.pose_estimator.time.monotonic_ns", lambda: 10_000_000)
    assert estimator.extract_landmarks("bgr") == []
    assert estimator.extract_landmarks("bgr") == []
    assert [call.args[1] for call in pose.detect_for_video.call_args_list] == [10, 11]
    cv2.cvtColor.assert_called_with("bgr", 1)
    mp.Image.assert_called_with(image_format="srgb", data="rgb")
    estimator.close()
    pose.close.assert_called_once()


def test_static_mode_and_landmark_format(tasks):
    _, _, pose, _ = tasks
    estimator = PoseEstimator(static_image_mode=True, model_complexity=2)
    pose.detect.return_value = SimpleNamespace(pose_landmarks=[[
        SimpleNamespace(x=0.1, y=0.2, z=-0.3, visibility=0.9),
        SimpleNamespace(x=0.4, y=0.5, z=0.6, visibility=None),
    ]])
    assert estimator.extract_landmarks("frame") == [
        {"x": 0.1, "y": 0.2, "z": -0.3, "visibility": 0.9},
        {"x": 0.4, "y": 0.5, "z": 0.6, "visibility": 0.0},
    ]
    pose.detect_for_video.assert_not_called()


def test_person_detection_uses_tasks_landmarks(tasks):
    _, _, pose, _ = tasks
    detector = PersonDetector()
    points = [SimpleNamespace(x=0.1, y=0.2, z=0.3, visibility=0.9) for _ in range(33)]
    pose.detect_for_video.return_value = SimpleNamespace(pose_landmarks=[points])
    assert len(detector.detect_with_landmarks("frame")) == 33
    assert detector.detect("frame") is True
    pose.detect_for_video.return_value = SimpleNamespace(pose_landmarks=[])
    assert detector.detect("frame") is False


def test_missing_model_has_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="POSE_MODEL_PATH"):
        PoseEstimator(model_path=str(tmp_path / "missing.task"))


def test_default_model_path_is_independent_of_working_directory(tasks, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    PoseEstimator()
    options = tasks[1].PoseLandmarker.create_from_options.call_args.args[0]
    assert options.base_options.model_asset_path.endswith("/models/pose_landmarker_lite.task")


def test_pose_model_configuration(monkeypatch):
    import importlib

    with monkeypatch.context() as env:
        env.delenv("POSE_MODEL_PATH", raising=False)
        importlib.reload(config)
        assert config.POSE_MODEL_PATH == "models/pose_landmarker_lite.task"
        env.setenv("POSE_MODEL_PATH", "/tmp/custom.task")
        importlib.reload(config)
        assert config.POSE_MODEL_PATH == "/tmp/custom.task"
    importlib.reload(config)
