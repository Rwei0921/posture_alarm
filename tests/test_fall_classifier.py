from vision.fall_classifier import FallClassifier


def _blank_landmarks() -> list[dict[str, float]]:
    return [
        {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99}
        for _ in range(33)
    ]


def _standing_landmarks() -> list[dict[str, float]]:
    points = _blank_landmarks()
    points[11].update({"x": 0.45, "y": 0.30})
    points[12].update({"x": 0.55, "y": 0.30})
    points[23].update({"x": 0.47, "y": 0.35})
    points[24].update({"x": 0.53, "y": 0.35})
    return points


def _fallen_landmarks() -> list[dict[str, float]]:
    points = _blank_landmarks()
    points[11].update({"x": 0.78, "y": 0.52})
    points[12].update({"x": 0.86, "y": 0.52})
    points[23].update({"x": 0.16, "y": 0.56})
    points[24].update({"x": 0.24, "y": 0.56})
    return points


def test_standing_pose_is_not_fall():
    classifier = FallClassifier(window_size=5, score_threshold=0.6)
    detected, features = classifier.classify(_standing_landmarks(), timestamp=1.0)
    assert detected is False
    assert features.trunk_angle_deg < 30


def test_fall_posture_triggers_detection():
    classifier = FallClassifier(window_size=1, score_threshold=0.6)
    classifier.classify(_standing_landmarks(), timestamp=1.0)
    detected, features = classifier.classify(_fallen_landmarks(), timestamp=1.3)
    assert detected is True
    assert features.trunk_angle_deg >= 60
    assert features.hip_shoulder_diff <= 0.10
    assert features.has_fall_event is True


def test_multi_frame_smoothing_logic():
    classifier = FallClassifier(window_size=5, score_threshold=0.6)

    seq = [
        _standing_landmarks(),
        _standing_landmarks(),
        _fallen_landmarks(),
        _fallen_landmarks(),
        _fallen_landmarks(),
    ]

    timestamps = [1.0, 2.0, 2.3, 2.6, 2.9]
    outputs = [classifier.classify(lm, timestamp=timestamps[idx])[0] for idx, lm in enumerate(seq)]

    assert outputs[0] is False
    assert outputs[1] is False
    assert outputs[2] is False
    assert outputs[3] is False
    assert outputs[4] is True


def test_slow_lie_down_not_detected_as_fall():
    classifier = FallClassifier(window_size=3, score_threshold=0.6, min_hip_drop=0.12)

    def lying_step(y_hip: float) -> list[dict[str, float]]:
        points = _blank_landmarks()
        points[11].update({"x": 0.72, "y": 0.55})
        points[12].update({"x": 0.80, "y": 0.55})
        points[23].update({"x": 0.20, "y": y_hip})
        points[24].update({"x": 0.28, "y": y_hip})
        return points

    outputs = [
        classifier.classify(lying_step(0.40), timestamp=1.0)[0],
        classifier.classify(lying_step(0.46), timestamp=2.0)[0],
        classifier.classify(lying_step(0.52), timestamp=3.0)[0],
        classifier.classify(lying_step(0.56), timestamp=4.0)[0],
    ]
    assert outputs == [False, False, False, False]


def test_tuned_thresholds_reduce_head_raise_false_positive():
    def reclined_pose(hip_y: float) -> list[dict[str, float]]:
        points = _blank_landmarks()
        points[11].update({"x": 0.74, "y": 0.52})
        points[12].update({"x": 0.82, "y": 0.52})
        points[23].update({"x": 0.20, "y": hip_y})
        points[24].update({"x": 0.28, "y": hip_y})
        return points

    old_classifier = FallClassifier(
        angle_threshold_deg=55.0,
        hip_shoulder_diff_threshold=0.12,
        speed_threshold=0.28,
        window_size=1,
        score_threshold=0.6,
        min_hip_drop=0.12,
        event_window_seconds=1.5,
    )
    tuned_classifier = FallClassifier(window_size=1, score_threshold=0.67)

    old_classifier.classify(reclined_pose(0.410), timestamp=1.0)
    tuned_classifier.classify(reclined_pose(0.410), timestamp=1.0)

    old_detected, old_features = old_classifier.classify(reclined_pose(0.554), timestamp=1.5)
    tuned_detected, tuned_features = tuned_classifier.classify(reclined_pose(0.554), timestamp=1.5)

    assert old_detected is True
    assert tuned_detected is False
    assert old_features.has_fall_event is True
    assert tuned_features.has_fall_event is False
