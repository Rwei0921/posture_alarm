"""Main application loop for posture alarm."""

from __future__ import annotations

import importlib
import signal
import time

import config
from alert.buzzer_led import BuzzerLED
from alert.notifier_line import LineNotifier
from alert.notifier_telegram import TelegramNotifier
from core.state_machine import PostureState, PostureStateMachine
from core.utils import setup_logger
from sensors.imu_mpu6050 import IMU_MPU6050
from storage.db_sqlite import EventDB
from storage.reporter import Reporter
from ui.overlay import Overlay
from vision.camera import Camera
from vision.fall_classifier import FallClassifier
from vision.person_detector import PersonDetector
from vision.pose_estimator import PoseEstimator


def _load_cv2():
    return importlib.import_module("cv2")


def _in_bed_roi(hip_center: tuple[float, float]) -> bool:
    if not config.BED_ROI_ENABLED:
        return False
    x, y = hip_center
    return (
        config.BED_ROI_X1 <= x <= config.BED_ROI_X2
        and config.BED_ROI_Y1 <= y <= config.BED_ROI_Y2
    )


def run() -> None:
    logger = setup_logger()
    stop_requested = False

    def _request_stop(signum: int, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True
        logger.info("received signal %s, shutting down", signum)

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    cam = Camera(
        config.CAMERA_SOURCE,
        config.CAMERA_WIDTH,
        config.CAMERA_HEIGHT,
        backend=config.CAMERA_BACKEND,
        warmup_frames=config.CAMERA_WARMUP_FRAMES,
        read_retry=config.CAMERA_READ_RETRY,
        rpicam_fps=config.RPICAM_FPS,
        rpicam_timeout_ms=config.RPICAM_TIMEOUT_MS,
        rpicam_buffer_max_bytes=config.RPICAM_BUFFER_MAX_BYTES,
    )
    person_detector = PersonDetector(
        visibility_threshold=config.POSE_VISIBILITY_THRESHOLD,
        min_visible_keypoints=config.MIN_VISIBLE_KEYPOINTS,
        min_detection_confidence=config.MP_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=config.MP_MIN_TRACKING_CONFIDENCE,
    )
    pose_estimator = PoseEstimator(
        static_image_mode=config.MP_STATIC_IMAGE_MODE,
        model_complexity=config.MP_MODEL_COMPLEXITY,
        min_detection_confidence=config.MP_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=config.MP_MIN_TRACKING_CONFIDENCE,
    )
    fall_classifier = FallClassifier(
        angle_threshold_deg=config.FALL_TRUNK_ANGLE_THRESHOLD_DEG,
        hip_shoulder_diff_threshold=config.FALL_HIP_SHOULDER_DIFF_THRESHOLD,
        speed_threshold=config.FALL_SPEED_THRESHOLD,
        window_size=config.FALL_SCORE_WINDOW_SIZE,
        score_threshold=config.FALL_SCORE_THRESHOLD,
        min_hip_drop=config.FALL_EVENT_MIN_HIP_DROP,
        event_window_seconds=config.FALL_EVENT_WINDOW_SECONDS,
    )
    state_machine = PostureStateMachine(
        suspect_timeout=config.SUSPECT_FALL_TIMEOUT,
        fall_confirm_seconds=config.FALL_CONFIRM_SECONDS,
        sedentary_seconds=config.SEDENTARY_SECONDS,
        recovery_seconds=config.FALL_RECOVERY_SECONDS,
    )
    imu = IMU_MPU6050(simulate=config.SIMULATE_IMU, shock_threshold_g=config.IMU_SHOCK_THRESHOLD_G)

    buzzer = BuzzerLED(simulate=config.SIMULATE_GPIO)
    line = LineNotifier(config.LINE_NOTIFY_TOKEN)
    telegram = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)

    db = EventDB(config.DB_PATH)
    reporter = Reporter(config.DB_PATH, str(config.REPORT_DIR))
    overlay = Overlay()

    cv2 = None
    if config.SHOW_WINDOW:
        cv2 = _load_cv2()

    previous_state = state_machine.state
    read_failures = 0
    last_alert_ts = 0.0
    logger.info("posture_alarm started")
    logger.info(
        "camera backend=%s source=%s size=%sx%s",
        config.CAMERA_BACKEND,
        config.CAMERA_SOURCE,
        config.CAMERA_WIDTH,
        config.CAMERA_HEIGHT,
    )

    try:
        while not stop_requested:
            ok, frame = cam.read_frame()
            if not ok:
                read_failures += 1
                if read_failures % 10 == 0:
                    logger.warning(
                        "camera frame unavailable (%s/%s)",
                        read_failures,
                        config.CAMERA_MAX_READ_FAILURES,
                    )
                if read_failures >= config.CAMERA_MAX_READ_FAILURES:
                    logger.warning("camera frame unavailable, stopping loop")
                    break
                time.sleep(0.05)
                continue
            read_failures = 0

            landmarks = pose_estimator.extract_landmarks(frame)
            person_present = person_detector.has_person(landmarks) if landmarks else False

            fall_detected = False
            hip_speed = 0.0
            if person_present:
                fall_detected, features = fall_classifier.classify(landmarks)
                hip_speed = features.hip_speed
                if fall_detected and _in_bed_roi((
                    (landmarks[23]["x"] + landmarks[24]["x"]) / 2.0,
                    features.hip_center_y,
                )) and not features.has_fall_event:
                    fall_detected = False

            motion_detected = hip_speed > 0.02 if person_present else False
            impact_detected = imu.detect_impact()

            state = state_machine.update(
                fall_detected=fall_detected,
                impact_detected=impact_detected,
                motion_detected=motion_detected,
            )

            if state != previous_state:
                logger.info("state changed: %s -> %s", previous_state, state)
                db.log_event(
                    event_type="state_change",
                    state=state.value,
                    payload={"previous_state": previous_state.value},
                )
                previous_state = state

            if state == PostureState.FALLEN:
                buzzer.alert_on()
                now_ts = time.monotonic()
                if (now_ts - last_alert_ts) >= config.ALERT_COOLDOWN_SECONDS:
                    db.log_event(event_type="fall", state=state.value, payload={"impact": impact_detected})
                    alert_msg = "Posture alarm: fall detected"
                    line.send(alert_msg)
                    telegram.send(alert_msg)
                    last_alert_ts = now_ts
            else:
                buzzer.alert_off()

            frame = overlay.draw_status(frame, state.value, warning=state == PostureState.FALLEN)
            if landmarks:
                frame = overlay.draw_landmarks(frame, landmarks)
            if config.BED_ROI_ENABLED and config.BED_ROI_SHOW:
                frame = overlay.draw_bed_roi(
                    frame,
                    config.BED_ROI_X1,
                    config.BED_ROI_Y1,
                    config.BED_ROI_X2,
                    config.BED_ROI_Y2,
                )
            if state == PostureState.FALLEN:
                frame = overlay.draw_alert(frame, "FALL DETECTED")

            if config.SHOW_WINDOW and cv2 is not None:
                display_frame = frame
                if config.DISPLAY_SCALE > 0 and config.DISPLAY_SCALE != 1.0:
                    display_frame = cv2.resize(
                        frame,
                        None,
                        fx=config.DISPLAY_SCALE,
                        fy=config.DISPLAY_SCALE,
                        interpolation=cv2.INTER_AREA,
                    )
                cv2.imshow("posture_alarm", display_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q"), 27):
                    logger.info("exit requested by keyboard")
                    stop_requested = True
                    break
                if cv2.getWindowProperty("posture_alarm", cv2.WND_PROP_VISIBLE) < 1:
                    logger.info("exit requested by window close")
                    stop_requested = True
                    break

            time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("received keyboard interrupt, shutting down")

    finally:
        cam.release()
        pose_estimator.close()
        person_detector.close()
        imu.close()
        buzzer.close()
        db.close()
        if cv2 is not None:
            cv2.destroyAllWindows()

        # Keep reporter instantiated and available for external scheduling/use.
        _ = reporter
        logger.info("posture_alarm stopped")


if __name__ == "__main__":
    run()
