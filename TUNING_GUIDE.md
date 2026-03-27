# posture_alarm Threshold Tuning Guide

This guide explains how to tune the main posture and fall parameters for hospital room and care facility scenarios.

## 1. Recommended baseline

Start with these values:

```bash
export FALL_TRUNK_ANGLE_THRESHOLD_DEG=55
export FALL_HIP_SHOULDER_DIFF_THRESHOLD=0.12
export FALL_SPEED_THRESHOLD=0.28
export FALL_SCORE_WINDOW_SIZE=5
export FALL_SCORE_THRESHOLD=0.6
export FALL_EVENT_MIN_HIP_DROP=0.12
export FALL_EVENT_WINDOW_SECONDS=1.5
export POSE_VISIBILITY_THRESHOLD=0.6
export MIN_VISIBLE_KEYPOINTS=10
export BED_ROI_ENABLED=1
export BED_ROI_X1=0.20
export BED_ROI_Y1=0.35
export BED_ROI_X2=0.90
export BED_ROI_Y2=0.95
```

## 2. What each threshold controls

- `FALL_TRUNK_ANGLE_THRESHOLD_DEG`: larger value means stricter horizontal-posture requirement.
- `FALL_HIP_SHOULDER_DIFF_THRESHOLD`: smaller value means stricter lying-flat requirement.
- `FALL_SPEED_THRESHOLD`: larger value means fewer sudden-fall detections from motion noise.
- `FALL_SCORE_WINDOW_SIZE`: more frames means smoother decision but slower response.
- `FALL_SCORE_THRESHOLD`: larger value reduces false alarms but may miss subtle falls.
- `FALL_EVENT_MIN_HIP_DROP`: minimum short-term hip vertical drop needed to mark a fall event.
- `FALL_EVENT_WINDOW_SECONDS`: how long a fall event can support later lying-posture confirmation.
- `POSE_VISIBILITY_THRESHOLD` and `MIN_VISIBLE_KEYPOINTS`: larger values reduce object-as-person false positives.
- `BED_ROI_*`: bed area ROI used to suppress bed-rest false positives.

## 3. Camera angle presets

### High-angle camera (ceiling corner)

```bash
export FALL_TRUNK_ANGLE_THRESHOLD_DEG=60
export FALL_HIP_SHOULDER_DIFF_THRESHOLD=0.10
export FALL_SPEED_THRESHOLD=0.30
export FALL_SCORE_WINDOW_SIZE=6
export FALL_SCORE_THRESHOLD=0.67
```

### Low-angle camera (bedside or wall)

```bash
export FALL_TRUNK_ANGLE_THRESHOLD_DEG=50
export FALL_HIP_SHOULDER_DIFF_THRESHOLD=0.14
export FALL_SPEED_THRESHOLD=0.24
export FALL_SCORE_WINDOW_SIZE=5
export FALL_SCORE_THRESHOLD=0.6
```

## 4. Data collection workflow

1. Run the app with current thresholds.
2. Collect `data/events.db` after real room simulation.
3. Export CSV with reporter:

```bash
python -c "from storage.reporter import Reporter; r=Reporter('data/events.db','reports'); print(r.generate_daily_report())"
```

4. Label false positives and false negatives.
5. Adjust one parameter group at a time, re-test, and compare results.

## 5. Common troubleshooting

- Too many false positives from objects: increase `POSE_VISIBILITY_THRESHOLD`, `MIN_VISIBLE_KEYPOINTS`, and `FALL_SCORE_THRESHOLD`.
- Patient lying down on bed still triggers fall: increase `FALL_EVENT_MIN_HIP_DROP`, reduce `FALL_EVENT_WINDOW_SECONDS`, and calibrate `BED_ROI_*`.
- Missed real falls: reduce `FALL_TRUNK_ANGLE_THRESHOLD_DEG` or `FALL_SCORE_THRESHOLD` slightly.
- Slow detection: reduce `FALL_SCORE_WINDOW_SIZE` from 6 to 4-5.
