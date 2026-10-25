"""Launch the optional control panel, or retain CLI monitoring without a display."""

from __future__ import annotations

import argparse
import importlib
import os

from core.control_settings import read_env
from core.runtime_paths import application_root, is_frozen


def launch(preview: bool = False) -> None:
    project = application_root()
    env_path = project / "demo.env"
    try:
        # 在匯入 config 前載入設定，獨立啟動也不需要手動 source demo.env。
        if not preview:
            os.environ.update(read_env(env_path))
        import config
        importlib.reload(config)
    except (ValueError, OSError):
        print("Cannot load demo.env. Check numeric values, quoting and file permissions.")
        return
    try:
        import tkinter as tk
    except ImportError:
        print("Tkinter is unavailable. On Raspberry Pi, install python3-tk. Continuing in CLI mode.")
        tk = None
    root = None
    if tk is not None:
        try:
            root = tk.Tk()
        except tk.TclError:
            print("No graphical display available. Continuing in CLI mode (no camera window).")
    if root is None:
        if not preview:
            config.SHOW_WINDOW = False
            config.BED_ROI_MARK_ON_START = False
            from main import run
            run()
        return
    try:
        from ui.control_panel import ControlPanel
        ControlPanel(root, project, env_path, config, preview=preview)
        root.mainloop()
    except Exception:
        root.destroy()
        raise


def main(argv: list[str] | None = None) -> int:
    if is_frozen():
        # 若套件需要 multiprocessing，先讓 PyInstaller 攔截其內部啟動參數。
        from multiprocessing import freeze_support
        freeze_support()
    parser = argparse.ArgumentParser(description="Posture Alarm control panel")
    parser.add_argument("--preview", action="store_true", help="Preview UI without camera, GPIO, notifications or saving")
    parser.add_argument("--worker", choices=("monitor", "camera", "alarm_test"), help=argparse.SUPPRESS)
    parser.add_argument("--self-test", action="store_true", help="Check packaged imports and model without opening hardware")
    args = parser.parse_args(argv)
    if args.worker:
        # 封裝後 sys.executable 是本程式，而不是可直接執行 .py 的 Python。
        from control_worker import worker
        return worker(args.worker)
    if args.self_test:
        try:
            import config
            # 明確保留兩個入口的匯入，讓封裝分析也能收錄監控與工作程序。
            import main as runtime
            from control_worker import worker
            for module in ("tkinter", "cv2", "numpy", "mediapipe", "gpiozero", "lgpio", "requests"):
                importlib.import_module(module)
            importlib.import_module("mediapipe").tasks.vision.PoseLandmarker
            if not (config.RESOURCE_DIR / "models" / "pose_landmarker_lite.task").is_file():
                raise FileNotFoundError("Bundled pose model missing")
        except Exception as exc:
            print(f"Self-test failed: {type(exc).__name__}. Check packaged dependencies and model.")
            return 1
        print("Self-test OK: imports and bundled pose model; hardware and notifications were not initialized.")
        return 0
    launch(preview=args.preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
