"""Main application loop for posture alarm."""

from __future__ import annotations

import importlib
import os
import signal
import time
from typing import Any, Callable, Protocol

import config
from alert.buzzer_led import BuzzerLED
from alert.notifier_discord import DiscordNotifier
from alert.notifier_line import LineNotifier
from core.state_machine import PostureState, PostureStateMachine
from core.utils import build_fall_alert_message, display_timestamp_from_iso, now_timestamp, setup_logger
from storage.db_sqlite import EventDB
from storage.reporter import Reporter
from sensors.dht22 import DHT22Reading, DHT22Sensor
from sensors.environment import EnvironmentSensor
from sensors.sht31 import SHT31Sensor
from ui.overlay import Overlay
from vision.camera import Camera
from vision.fall_classifier import FallClassifier
from vision.person_detector import PersonDetector
from vision.pose_estimator import PoseEstimator


def _load_cv2():
    if os.name != "nt":
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
        os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")
    return importlib.import_module("cv2")


def _in_bed_roi(hip_center: tuple[float, float]) -> bool:
    x, y = hip_center

    if config.BED_POLYGON_ENABLED:
        polygon = _bed_polygon_points()
        return _point_in_polygon((x, y), polygon)

    if not config.BED_ROI_ENABLED:
        return False

    return (
        config.BED_ROI_X1 <= x <= config.BED_ROI_X2
        and config.BED_ROI_Y1 <= y <= config.BED_ROI_Y2
    )


def _bed_polygon_points() -> list[tuple[float, float]]:
    return [
        (config.BED_POLY_P1_X, config.BED_POLY_P1_Y),
        (config.BED_POLY_P2_X, config.BED_POLY_P2_Y),
        (config.BED_POLY_P3_X, config.BED_POLY_P3_Y),
        (config.BED_POLY_P4_X, config.BED_POLY_P4_Y),
    ]


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    if len(polygon) < 3:
        return False

    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < ((xj - xi) * (y - yi) / ((yj - yi) + 1e-12) + xi)
        )
        if intersect:
            inside = not inside
        j = i
    return inside


class _MessageSender(Protocol):
    def send(self, message: str) -> bool:
        ...


def _send_fall_alert(
    db: EventDB,
    line: _MessageSender,
    discord: _MessageSender,
    logger,
    payload: dict[str, Any] | None = None,
) -> bool:
    event_ts = now_timestamp()
    alert_msg = build_fall_alert_message(display_timestamp_from_iso(event_ts))
    line_sent = line.send(alert_msg)
    discord_sent = discord.send(alert_msg)
    message_sent = line_sent or discord_sent
    event_payload = {
        "source": "vision",
        "alert_level": "critical",
        **(payload or {}),
        "line_sent": line_sent,
        "discord_sent": discord_sent,
        "message_sent": message_sent,
    }
    db.log_event(
        event_type="fall",
        state=PostureState.FALLEN.value,
        payload=event_payload,
        ts=event_ts,
    )
    logger.info(
        "fall alert sent: line=%s discord=%s",
        line_sent,
        discord_sent,
    )
    return message_sent


def _interactive_mark_bed_roi(
    cam: Camera, cv2, scale: float, logger,
    should_stop: Callable[[], bool] = lambda: False,
) -> bool:
    scale = scale if scale > 0 else 1.0
    window = "Mark BED ROI"
    window_initialized = False

    logger.info("BED ROI marker: click 4 corners (TL->TR->BR->BL), ENTER=confirm, R=reset, Q=skip")
    points: list[tuple[float, float]] = []
    mouse_state: dict[str, Any] = {"frame_shape": None}

    def _mouse_cb(event, x, y, _flags, _param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if len(points) >= 4:
            return
        frame_shape = mouse_state.get("frame_shape")
        if frame_shape is None:
            return
        fh, fw = frame_shape
        nx = max(0.0, min(1.0, (x / scale) / fw))
        ny = max(0.0, min(1.0, (y / scale) / fh))
        points.append((nx, ny))

    read_failures = 0
    while not should_stop():
        ok, frame = cam.read_frame()
        if should_stop():
            break
        if not ok:
            read_failures += 1
            if read_failures >= config.CAMERA_MAX_READ_FAILURES:
                logger.warning("camera frame unavailable, aborting BED ROI marker")
                if window_initialized:
                    cv2.destroyWindow(window)
                return False
            time.sleep(0.05)
            continue
        read_failures = 0

        if not window_initialized:
            h, w = frame.shape[:2]
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window, int(w * scale), int(h * scale))
            cv2.setMouseCallback(window, _mouse_cb)
            window_initialized = True

        mouse_state["frame_shape"] = frame.shape[:2]
        preview = frame.copy()
        h, w = preview.shape[:2]
        pixel_points = [(int(px * w), int(py * h)) for px, py in points]

        for idx, p in enumerate(pixel_points):
            cv2.circle(preview, p, 5, (0, 170, 255), -1)
            cv2.putText(
                preview,
                str(idx + 1),
                (p[0] + 6, p[1] - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 170, 255),
                2,
                cv2.LINE_AA,
            )

        if len(pixel_points) >= 2:
            cv2.polylines(
                preview,
                [importlib.import_module("numpy").array(pixel_points, dtype="int32")],
                len(pixel_points) == 4,
                (0, 170, 255),
                2,
            )

        if scale != 1.0:
            preview = cv2.resize(preview, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        cv2.putText(
            preview,
            "Click 4 corners | ENTER: confirm | R: reset | Q: skip",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(window, preview)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break

        if key in (ord("r"), ord("R")):
            points.clear()
            continue

        if key in (13, 10, 32):
            if len(points) != 4:
                logger.info("Please click exactly 4 points before confirm")
                continue

            config.BED_POLYGON_ENABLED = True
            config.BED_POLY_P1_X, config.BED_POLY_P1_Y = points[0]
            config.BED_POLY_P2_X, config.BED_POLY_P2_Y = points[1]
            config.BED_POLY_P3_X, config.BED_POLY_P3_Y = points[2]
            config.BED_POLY_P4_X, config.BED_POLY_P4_Y = points[3]

            # Backward-compatible rectangle bounds for existing tooling.
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            config.BED_ROI_ENABLED = True
            config.BED_ROI_X1 = min(xs)
            config.BED_ROI_Y1 = min(ys)
            config.BED_ROI_X2 = max(xs)
            config.BED_ROI_Y2 = max(ys)

            logger.info(
                "BED polygon set: (%.4f,%.4f) (%.4f,%.4f) (%.4f,%.4f) (%.4f,%.4f)",
                points[0][0], points[0][1],
                points[1][0], points[1][1],
                points[2][0], points[2][1],
                points[3][0], points[3][1],
            )
            break

    if window_initialized:
        cv2.destroyWindow(window)
    return not should_stop()


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
        model_path=config.POSE_MODEL_PATH,
    )
    pose_estimator = PoseEstimator(
        static_image_mode=config.MP_STATIC_IMAGE_MODE,
        model_complexity=config.MP_MODEL_COMPLEXITY,
        min_detection_confidence=config.MP_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=config.MP_MIN_TRACKING_CONFIDENCE,
        model_path=config.POSE_MODEL_PATH,
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

    buzzer = BuzzerLED(
        simulate=config.SIMULATE_GPIO,
        buzzer_pwm=config.BUZZER_PWM_ENABLED,
        buzzer_frequency=config.BUZZER_PWM_FREQUENCY,
        buzzer_pin=config.BUZZER_GPIO_PIN,
        led_pin=config.LED_GPIO_PIN,
        led_2_pin=config.LED_2_GPIO_PIN,
        led_2_enabled=config.LED_2_ENABLED,
    )
    if config.ENV_SENSOR_BACKEND not in ("sht31", "dht22", "none"):
        raise ValueError("ENV_SENSOR_BACKEND must be sht31, dht22, or none")
    dht22 = None
    if config.ENV_SENSOR_BACKEND == "sht31":
        fallback = DHT22Sensor(
            data_pin=config.DHT22_DATA_PIN,
            simulate=config.SIMULATE_GPIO,
            use_pulseio=config.DHT22_USE_PULSEIO,
        ) if config.DHT22_FALLBACK_ENABLED and config.DHT22_ENABLED else None
        dht22 = EnvironmentSensor(
            SHT31Sensor(config.SHT31_I2C_BUS, config.SHT31_I2C_ADDRESS, config.SIMULATE_GPIO),
            fallback,
        )
    elif config.ENV_SENSOR_BACKEND == "dht22" and config.DHT22_ENABLED:
        dht22 = DHT22Sensor(
            data_pin=config.DHT22_DATA_PIN,
            simulate=config.SIMULATE_GPIO,
            use_pulseio=config.DHT22_USE_PULSEIO,
        )
    line = LineNotifier(
        channel_access_token=config.LINE_CHANNEL_ACCESS_TOKEN,
        to=config.LINE_TARGET_ID,
    )
    discord = DiscordNotifier(config.DISCORD_WEBHOOK_URL)

    db = EventDB(config.DB_PATH)
    reporter = Reporter(config.DB_PATH, str(config.REPORT_DIR))
    overlay = Overlay()

    cv2 = None
    if config.SHOW_WINDOW or config.BED_ROI_MARK_ON_START:
        cv2 = _load_cv2()

    previous_state = state_machine.state
    read_failures = 0
    last_alert_ts = float("-inf")
    last_dht_read_ts = 0.0
    last_dht_log_ts = 0.0
    last_dht_error_log_ts = 0.0
    last_dht_reading: DHT22Reading | None = None
    logger.info("posture_alarm started")
    if config.LOG_FILE_ENABLED:
        logger.info("file logging enabled: %s", config.LOG_FILE_PATH)
    else:
        logger.warning("file logging disabled: LOG_FILE_ENABLED=0")
    logger.info(
        "camera backend=%s source=%s size=%sx%s",
        config.CAMERA_BACKEND,
        config.CAMERA_SOURCE,
        config.CAMERA_WIDTH,
        config.CAMERA_HEIGHT,
    )
    logger.info(
        "gpio simulate=%s buzzer_pin=%s led_pin=%s led_2_pin=%s led_2_enabled=%s buzzer_pwm=%s buzzer_frequency=%.0fHz",
        config.SIMULATE_GPIO,
        config.BUZZER_GPIO_PIN,
        config.LED_GPIO_PIN,
        config.LED_2_GPIO_PIN,
        config.LED_2_ENABLED,
        config.BUZZER_PWM_ENABLED,
        config.BUZZER_PWM_FREQUENCY,
    )
    if dht22 is None:
        logger.info("Environment sensor disabled")
    elif dht22.available:
        logger.info("Environment sensor enabled: %s", config.ENV_SENSOR_BACKEND)
    elif config.SIMULATE_GPIO:
        logger.info("Environment sensor simulation mode: no physical sensor read")
    else:
        logger.warning("Environment sensor unavailable: %s", dht22.last_error or "unknown initialization error")
    line_configured = bool(config.LINE_CHANNEL_ACCESS_TOKEN and config.LINE_TARGET_ID)
    discord_configured = bool(config.DISCORD_WEBHOOK_URL)
    if line_configured:
        logger.info("LINE notifier enabled")
    else:
        logger.warning("LINE notifier disabled: set LINE_CHANNEL_ACCESS_TOKEN and LINE_TARGET_ID")
    if discord_configured:
        logger.info("Discord notifier enabled")
    else:
        logger.warning("Discord notifier disabled: set DISCORD_WEBHOOK_URL")
    if config.BED_ROI_ENABLED:
        if config.BED_POLYGON_ENABLED:
            pts = _bed_polygon_points()
            logger.info(
                "bed polygon enabled: (%.3f,%.3f) (%.3f,%.3f) (%.3f,%.3f) (%.3f,%.3f)",
                pts[0][0], pts[0][1], pts[1][0], pts[1][1], pts[2][0], pts[2][1], pts[3][0], pts[3][1]
            )
        else:
            logger.info(
                "bed roi enabled: x1=%.3f y1=%.3f x2=%.3f y2=%.3f",
                config.BED_ROI_X1,
                config.BED_ROI_Y1,
                config.BED_ROI_X2,
                config.BED_ROI_Y2,
            )

    try:
        if config.BED_ROI_MARK_ON_START:
            if cv2 is None:
                logger.warning("BED_ROI_MARK_ON_START=1 but OpenCV GUI is unavailable")
            else:
                if not _interactive_mark_bed_roi(
                    cam, cv2, config.BED_ROI_MARK_SCALE, logger, lambda: stop_requested,
                ):
                    return

        if config.SHOW_WINDOW and cv2 is not None:
            display_scale = config.DISPLAY_SCALE if config.DISPLAY_SCALE > 0 else 1.0
            window_w = int(config.CAMERA_WIDTH * display_scale)
            window_h = int(config.CAMERA_HEIGHT * display_scale)
            cv2.namedWindow("posture_alarm", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("posture_alarm", max(window_w, 320), max(window_h, 240))

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

            monotonic_now = time.monotonic()
            if (
                dht22 is not None
                and dht22.available
                and monotonic_now - last_dht_read_ts >= config.ENV_READ_INTERVAL_SECONDS
            ):
                last_dht_read_ts = monotonic_now
                reading = dht22.read()
                if reading is not None:
                    last_dht_reading = reading
                    if monotonic_now - last_dht_log_ts >= config.ENV_LOG_INTERVAL_SECONDS:
                        logger.info(
                            "Environment temperature=%.1fC humidity=%.1f%%",
                            reading.temperature_c,
                            reading.humidity_pct,
                        )
                        last_dht_log_ts = monotonic_now
                elif monotonic_now - last_dht_error_log_ts >= config.ENV_LOG_INTERVAL_SECONDS:
                    logger.warning("Environment sensor read failed: %s", dht22.last_error or "unknown read error")
                    last_dht_error_log_ts = monotonic_now

            landmarks = pose_estimator.extract_landmarks(frame)
            person_present = person_detector.has_person(landmarks) if landmarks else False
            fall_payload: dict[str, Any] = {"person_present": person_present}
            if last_dht_reading is not None:
                fall_payload.update({
                    "temperature_c": round(last_dht_reading.temperature_c, 2),
                    "humidity_pct": round(last_dht_reading.humidity_pct, 2),
                })

            fall_detected = False
            hip_speed = 0.0
            safe_lying_detected = False
            if person_present:
                fall_detected, features = fall_classifier.classify(landmarks)
                hip_speed = features.hip_speed
                in_bed_roi = _in_bed_roi((
                    (landmarks[23]["x"] + landmarks[24]["x"]) / 2.0,
                    features.hip_center_y,
                ))
                safe_lying_detected = fall_detected and in_bed_roi and not features.has_fall_event
                fall_payload.update({
                    "trunk_angle_deg": round(features.trunk_angle_deg, 3),
                    "hip_shoulder_diff": round(features.hip_shoulder_diff, 3),
                    "hip_speed": round(features.hip_speed, 3),
                    "fall_score": round(features.fall_score, 3),
                    "has_fall_event": features.has_fall_event,
                    "in_bed_roi": in_bed_roi,
                    "safe_lying_detected": safe_lying_detected,
                })
                if fall_detected and safe_lying_detected:
                    fall_detected = False

            motion_detected = hip_speed > 0.02 if person_present else False

            state = state_machine.update(
                fall_detected=fall_detected,
                motion_detected=motion_detected,
                safe_lying_detected=safe_lying_detected,
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
                    last_alert_ts = now_ts
                    _send_fall_alert(db, line, discord, logger, fall_payload)
            else:
                buzzer.alert_off()

            frame = overlay.draw_status(frame, state.value, warning=state == PostureState.FALLEN)
            if dht22 is not None and config.ENV_SHOW:
                frame = overlay.draw_environment(
                    frame,
                    last_dht_reading.temperature_c if last_dht_reading else None,
                    last_dht_reading.humidity_pct if last_dht_reading else None,
                )
            if landmarks:
                frame = overlay.draw_landmarks(frame, landmarks)
            if config.BED_ROI_ENABLED and config.BED_ROI_SHOW:
                if config.BED_POLYGON_ENABLED:
                    frame = overlay.draw_bed_polygon(frame, _bed_polygon_points())
                else:
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
                if key in (ord("m"), ord("M")):
                    logger.info("manual BED ROI re-mark requested")
                    if not _interactive_mark_bed_roi(
                        cam, cv2, config.BED_ROI_MARK_SCALE, logger, lambda: stop_requested,
                    ):
                        break
                    continue
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
        buzzer.close()
        if dht22 is not None:
            dht22.close()
        db.close()
        if cv2 is not None:
            cv2.destroyAllWindows()

        # Keep reporter instantiated and available for external scheduling/use.
        _ = reporter
        logger.info("posture_alarm stopped")


if __name__ == "__main__":
    run()
