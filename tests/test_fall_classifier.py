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
    points[23].update({"x": 0.47, "y": 0.65})
    points[24].update({"x": 0.53, "y": 0.65})
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
    detected, features = classifier.classify(_fallen_landmarks(), timestamp=1.0)
    assert detected is True
    assert features.trunk_angle_deg >= 55
    assert features.hip_shoulder_diff <= 0.12


def test_multi_frame_smoothing_logic():
    classifier = FallClassifier(window_size=5, score_threshold=0.6)

    seq = [
        _standing_landmarks(),
        _standing_landmarks(),
        _fallen_landmarks(),
        _fallen_landmarks(),
        _fallen_landmarks(),
    ]

    outputs = [classifier.classify(lm, timestamp=idx + 1.0)[0] for idx, lm in enumerate(seq)]

    assert outputs[0] is False
    assert outputs[1] is False
    assert outputs[2] is False
    assert outputs[3] is False
    assert outputs[4] is True
