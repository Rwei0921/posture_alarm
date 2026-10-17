"""Launch the optional control panel, or retain CLI monitoring without a display."""

from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path

from core.control_settings import read_env


def launch(preview: bool = False) -> None:
    project = Path(__file__).resolve().parent
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Posture Alarm control panel")
    parser.add_argument("--preview", action="store_true", help="Preview UI without camera, GPIO, notifications or saving")
    launch(preview=parser.parse_args().preview)
