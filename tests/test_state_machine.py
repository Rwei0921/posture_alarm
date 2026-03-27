from core.state_machine import PostureState, PostureStateMachine


def test_normal_to_suspect_to_fallen_path():
    sm = PostureStateMachine(suspect_timeout=2.0, fall_confirm_seconds=1.0, sedentary_seconds=100.0)
    t0 = 10.0

    assert sm.update(fall_detected=False, impact_detected=False, motion_detected=True, now=t0) == PostureState.NORMAL
    assert sm.update(fall_detected=True, impact_detected=False, motion_detected=True, now=t0 + 0.1) == PostureState.SUSPECT_FALL
    assert sm.update(fall_detected=True, impact_detected=False, motion_detected=False, now=t0 + 1.2) == PostureState.FALLEN


def test_suspect_timeout_back_to_normal():
    sm = PostureStateMachine(suspect_timeout=1.0, fall_confirm_seconds=0.8, sedentary_seconds=100.0)
    t0 = 20.0

    assert sm.update(fall_detected=True, impact_detected=False, motion_detected=True, now=t0) == PostureState.SUSPECT_FALL
    assert sm.update(fall_detected=False, impact_detected=False, motion_detected=True, now=t0 + 1.2) == PostureState.NORMAL


def test_fallen_recovery_to_normal():
    sm = PostureStateMachine(
        suspect_timeout=1.0,
        fall_confirm_seconds=0.5,
        sedentary_seconds=100.0,
        recovery_seconds=1.0,
    )
    t0 = 30.0

    assert sm.update(fall_detected=True, impact_detected=True, motion_detected=True, now=t0) == PostureState.SUSPECT_FALL
    assert sm.update(fall_detected=True, impact_detected=False, motion_detected=False, now=t0 + 0.8) == PostureState.FALLEN
    assert sm.update(fall_detected=False, impact_detected=False, motion_detected=True, now=t0 + 2.0) == PostureState.NORMAL


def test_sedentary_detect_and_recover():
    sm = PostureStateMachine(suspect_timeout=1.0, fall_confirm_seconds=0.5, sedentary_seconds=2.0)
    t0 = 40.0

    assert sm.update(fall_detected=False, impact_detected=False, motion_detected=True, now=t0) == PostureState.NORMAL
    assert sm.update(fall_detected=False, impact_detected=False, motion_detected=False, now=t0 + 2.1) == PostureState.SEDENTARY
    assert sm.update(fall_detected=False, impact_detected=False, motion_detected=True, now=t0 + 2.2) == PostureState.NORMAL
