# posture_alarm Handoff

Last updated: 2026-04-09

## What is implemented
- Replaced YOLO-based plan with pure MediaPipe pipeline.
- Built core modules: camera input, person detection, pose extraction, fall classifier, state machine.
- Added alert/notifier/storage/ui modules with simulation-friendly defaults.
- Wired everything in `main.py` and validated import health (`All imports OK`).
- Added alert cooldown (`ALERT_COOLDOWN_SECONDS`) and scored multi-frame fall smoothing.
- Added event-window fall gating (`FALL_EVENT_MIN_HIP_DROP`, `FALL_EVENT_WINDOW_SECONDS`) and bed ROI suppression (`BED_ROI_*`) to reduce slow-lie false positives.
- Switched notifications to `LINE Messaging API + Discord webhook` and removed Telegram from the runtime path.
- Connected SQLite fully so DB file/schema bootstrap automatically and `Reporter` reads the same DB.
- Unified log / DB / alert timestamps with `APP_TIMEZONE` and changed outbound alert text to Chinese time format.
- Applied a first-pass conservative tuning of fall thresholds to reduce bed/reclining head-lift false positives.
- Added test suite (`tests/`) for state machine, classifier, DB, notifier, config, and utils.
- Added deployment/unit files (`posture_alarm.service`) and tuning guide (`TUNING_GUIDE.md`).

## Current runtime flow
`Camera -> PoseEstimator -> PersonDetector/ FallClassifier -> PostureStateMachine -> Alert + Notify + DB + Overlay`

## Key files
- `main.py`: app loop and module orchestration.
- `config.py`: thresholds, camera source, timezone, notifier credentials, storage paths.
- `vision/*.py`: camera, person detection, pose landmarks, fall rules.
- `core/state_machine.py`: `NORMAL`, `SUSPECT_FALL`, `FALLEN`, `SEDENTARY` transitions.
- `core/utils.py`: logger, timezone-aware timestamps, and alert message formatting.
- `storage/db_sqlite.py`: SQLite event log.
- `storage/reporter.py`: daily/weekly CSV report generation.
- `PROJECT_STATUS.md`: full project status and roadmap.

## How to run
1. Raspberry Pi one-shot install: `./install_rpi.sh`
2. Start app: `python main.py`

Optional environment variables:
- `CAMERA_BACKEND` (`auto` / `rpicam` / `picamera2` / `opencv`)
- `CAMERA_SOURCE`, `SHOW_WINDOW`
- `APP_TIMEZONE` (default `Asia/Taipei`)
- `SIMULATE_IMU`, `SIMULATE_GPIO`
- `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_TARGET_ID`
- `DISCORD_WEBHOOK_URL`
- `LOG_FILE_ENABLED`, `LOG_FILE_PATH`

For Raspberry Pi Camera Module 3, prefer `CAMERA_BACKEND=rpicam`.

Exit controls:
- Window mode: `q`, `Q`, or `Esc`
- Terminal mode: `Ctrl+C`

If camera process appears stuck:
- `pkill -f "python main.py"`
- `pkill -f rpicam-vid`

## Known gaps
- Fall detection is rule-based and needs real-world threshold tuning.
- Current threshold tuning is only a first pass; bed-side / reclining edge cases still need real footage validation.
- Alert cooldown can still suppress retries after a send failure, because cooldown advances on the alert path.
- Hardware-specific MPU6050 register decode is still a skeleton.

## Recommended next steps
1. Validate the new conservative fall thresholds on-device and refine `BED_ROI_*` for the real camera angle.
2. Add a distinct safe-in-bed state such as `LYING_SAFE` to separate normal bed rest from true falls.
3. Add integration / long-running tests for notifier delivery, cooldown behavior, and Raspberry Pi runtime stability.
4. Complete the real MPU6050 register read path if IMU hardware will be used in production.
