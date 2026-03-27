"""Interactive helper to mark BED ROI coordinates."""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
import time

import config
from vision.camera import Camera


def _load_cv2():
    if os.name != "nt":
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
        os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")
    return importlib.import_module("cv2")


def _run_marker(display_scale: float = 0.5) -> tuple[float, float, float, float] | None:
    cv2 = _load_cv2()
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

    window = "Mark BED ROI"
    print("Press SPACE to freeze frame and draw BED ROI.")
    print("Inside ROI selector: drag rectangle and press ENTER/SPACE to confirm, ESC to cancel.")
    print("Press Q to exit without changes.")
    print(f"Display scale: {display_scale}")

    selected: tuple[float, float, float, float] | None = None

    try:
        while True:
            ok, frame = cam.read_frame()
            if not ok:
                time.sleep(0.05)
                continue

            preview = frame.copy()
            if selected is not None:
                x1, y1, x2, y2 = selected
                h, w = preview.shape[:2]
                p1 = (int(x1 * w), int(y1 * h))
                p2 = (int(x2 * w), int(y2 * h))
                cv2.rectangle(preview, p1, p2, (0, 170, 255), 2)

            if display_scale != 1.0:
                preview = cv2.resize(
                    preview,
                    None,
                    fx=display_scale,
                    fy=display_scale,
                    interpolation=cv2.INTER_AREA,
                )

            cv2.putText(
                preview,
                "SPACE: select ROI  |  Q: quit",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(window, preview)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q"), 27):
                break

            if key == 32:  # space
                frozen = frame
                if display_scale != 1.0:
                    frozen = cv2.resize(
                        frame,
                        None,
                        fx=display_scale,
                        fy=display_scale,
                        interpolation=cv2.INTER_AREA,
                    )

                roi = cv2.selectROI(window, frozen, fromCenter=False, showCrosshair=True)
                x, y, w, h = [int(v) for v in roi]
                if w > 0 and h > 0:
                    fh, fw = frame.shape[:2]
                    x1 = max(0.0, min(1.0, (x / display_scale) / fw))
                    y1 = max(0.0, min(1.0, (y / display_scale) / fh))
                    x2 = max(0.0, min(1.0, ((x + w) / display_scale) / fw))
                    y2 = max(0.0, min(1.0, ((y + h) / display_scale) / fh))
                    selected = (x1, y1, x2, y2)
                    print("\nUse these environment variables:")
                    print("export BED_ROI_ENABLED=1")
                    print(f"export BED_ROI_X1={x1:.4f}")
                    print(f"export BED_ROI_Y1={y1:.4f}")
                    print(f"export BED_ROI_X2={x2:.4f}")
                    print(f"export BED_ROI_Y2={y2:.4f}")

    finally:
        cam.release()
        cv2.destroyAllWindows()

    return selected


def _run_main_with_roi(roi: tuple[float, float, float, float]) -> int:
    x1, y1, x2, y2 = roi
    env = os.environ.copy()
    env["BED_ROI_ENABLED"] = "1"
    env["BED_ROI_X1"] = f"{x1:.4f}"
    env["BED_ROI_Y1"] = f"{y1:.4f}"
    env["BED_ROI_X2"] = f"{x2:.4f}"
    env["BED_ROI_Y2"] = f"{y2:.4f}"

    print("\nLaunching main.py with selected BED ROI...")
    return subprocess.call([sys.executable, "main.py"], env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark BED ROI and optionally start main.py")
    parser.add_argument(
        "--run-main",
        action="store_true",
        help="Start main.py immediately after selecting BED ROI",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=0.5,
        help="Preview display scale for ROI marker",
    )
    args = parser.parse_args()

    selected = _run_marker(display_scale=args.scale)

    if args.run_main:
        if selected is None:
            print("No ROI selected. main.py not started.")
            return
        code = _run_main_with_roi(selected)
        if code != 0:
            raise SystemExit(code)


if __name__ == "__main__":
    main()
