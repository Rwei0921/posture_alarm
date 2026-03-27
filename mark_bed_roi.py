"""Interactive helper to mark BED ROI coordinates."""

from __future__ import annotations

import importlib
import time

import config
from vision.camera import Camera


def _load_cv2():
    return importlib.import_module("cv2")


def main() -> None:
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

    selected = None

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
                roi = cv2.selectROI(window, frame, fromCenter=False, showCrosshair=True)
                x, y, w, h = [int(v) for v in roi]
                if w > 0 and h > 0:
                    fh, fw = frame.shape[:2]
                    x1 = x / fw
                    y1 = y / fh
                    x2 = (x + w) / fw
                    y2 = (y + h) / fh
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


if __name__ == "__main__":
    main()
