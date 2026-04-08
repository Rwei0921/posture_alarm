# posture_alarm Handoff

Last updated: 2026-03-19

## What is implemented
- Replaced YOLO-based plan with pure MediaPipe pipeline.
- Built core modules: camera input, person detection, pose extraction, fall classifier, state machine.
- Added alert/notifier/storage/ui modules with simulation-friendly defaults.
- Wired everything in `main.py` and validated import health (`All imports OK`).
- Added alert cooldown (`ALERT_COOLDOWN_SECONDS`) and scored multi-frame fall smoothing.
- Added event-window fall gating (`FALL_EVENT_MIN_HIP_DROP`, `FALL_EVENT_WINDOW_SECONDS`) and bed ROI suppression (`BED_ROI_*`) to reduce slow-lie false positives.
- Added test suite (`tests/`) for state machine, classifier, and DB.
- Added deployment/unit files (`posture_alarm.service`) and tuning guide (`TUNING_GUIDE.md`).

## Current runtime flow
`Camera -> PoseEstimator -> PersonDetector/ FallClassifier -> PostureStateMachine -> Alert + Notify + DB + Overlay`

## Key files
- `main.py`: app loop and module orchestration.
- `config.py`: thresholds, camera source, tokens, storage paths.
- `vision/*.py`: camera, person detection, pose landmarks, fall rules.
- `core/state_machine.py`: `NORMAL`, `SUSPECT_FALL`, `FALLEN`, `SEDENTARY` transitions.
- `storage/db_sqlite.py`: SQLite event log.
- `storage/reporter.py`: daily/weekly CSV report generation.
- `PROJECT_STATUS.md`: full project status and roadmap.

## How to run
1. Raspberry Pi one-shot install: `./install_rpi.sh`
2. Start app: `python main.py`

Optional environment variables:
- `CAMERA_BACKEND` (`auto` / `rpicam` / `picamera2` / `opencv`)
- `CAMERA_SOURCE`, `SHOW_WINDOW`
- `SIMULATE_IMU`, `SIMULATE_GPIO`
- `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_TARGET_ID`
- `DISCORD_WEBHOOK_URL`

For Raspberry Pi Camera Module 3, prefer `CAMERA_BACKEND=rpicam`.

Exit controls:
- Window mode: `q`, `Q`, or `Esc`
- Terminal mode: `Ctrl+C`

If camera process appears stuck:
- `pkill -f "python main.py"`
- `pkill -f rpicam-vid`

## Known gaps
- Fall detection is rule-based and needs real-world threshold tuning.
- Alert notify path can send repeated messages in sustained `FALLEN` state.
- Hardware-specific MPU6050 register decode is still a skeleton.

## Recommended next steps
1. Add notifier cooldown/dedup logic.
2. Add multi-frame smoothing/scoring for fall decisions.
3. Add unit tests for state machine, classifier, and DB.
4. Add headless deployment notes (systemd) for Raspberry Pi.
