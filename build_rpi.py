"""Build native Raspberry Pi bundles without collecting private runtime files."""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import importlib.util
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
MODEL = Path("models/pose_landmarker_lite.task")
REQUIRED_MODULES = ("tkinter", "cv2", "numpy", "mediapipe", "requests", "gpiozero", "lgpio")


def preflight() -> None:
    """只檢查匯入與檔案，不開鏡頭、不操作 GPIO，也不讀取 demo.env。"""
    if (sys.platform != "linux" or platform.machine().lower() not in {"aarch64", "arm64"}
            or sys.maxsize <= 2**32):
        raise RuntimeError("Build on 64-bit ARM Raspberry Pi OS, using the Pi's working virtual environment.")
    if not (ROOT / MODEL).is_file():
        raise RuntimeError("Missing models/pose_landmarker_lite.task; restore the tracked model first.")
    if importlib.util.find_spec("PyInstaller") is None:
        raise RuntimeError("Install build tools first: .venv/bin/python -m pip install -r requirements_build.txt")
    for name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(name)
            if name == "mediapipe":
                module.tasks.vision.PoseLandmarker
        except Exception:
            raise RuntimeError(f"Cannot import required module {name}; repair the existing Pi environment first.") from None
    if shutil.which("rpicam-vid") is None:
        raise RuntimeError("rpicam-vid is missing; install Raspberry Pi OS rpicam-apps first.")


def build_command(mode: str, work: Path, destination: Path) -> list[str]:
    """只收錄指定模型與程式相依套件，絕不整包加入專案目錄。"""
    if mode not in {"onedir", "onefile"}:
        raise ValueError("Unsupported bundle mode")
    command = [
        sys.executable, "-m", "PyInstaller", f"--{mode}",
        "--name", "posture_alarm", "--noupx",
        "--distpath", str(destination), "--workpath", str(work / "work"),
        "--specpath", str(work),
        "--add-data", f"{ROOT / MODEL}:models",
        "--collect-all", "mediapipe", "--collect-submodules", "gpiozero.pins",
        "--exclude-module", "pytest",
    ]
    for name in REQUIRED_MODULES:
        command.extend(("--hidden-import", name))
    # SHT31 以動態匯入使用 Linux i2c-dev；lgpio 的 SWIG 擴充也需明確收錄。
    for name in ("fcntl", "_lgpio"):
        command.extend(("--hidden-import", name))
    # 保留已安裝的選用後端，不為封裝額外安裝或升級它們。
    for name in ("picamera2", "adafruit_dht"):
        if importlib.util.find_spec(name) is not None:
            command.extend(("--collect-all", name))
            if name == "adafruit_dht":
                command.extend(("--hidden-import", "board", "--collect-all", "adafruit_blinka",
                                "--collect-all", "adafruit_platformdetect"))
    command.append(str(ROOT / "run_gui.py"))
    return command


def desktop_entry(executable: Path) -> str:
    """Exec 使用 desktop-entry 引號規則，不交給 shell 解譯。"""
    raw = str(executable.resolve())
    if any(character in raw for character in "\n\r\t"):
        raise ValueError("Desktop launcher paths cannot contain control characters")
    quoted = raw.replace("%", "%%").replace("\\", "\\\\\\\\")
    for character in ('"', '`', '$'):
        quoted = quoted.replace(character, "\\\\" + character)
    return (
        "[Desktop Entry]\nType=Application\nName=Posture Alarm\n"
        "Comment=Camera posture alarm control panel\n"
        f'Exec="{quoted}"\nTerminal=false\nCategories=Utility;\n'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Native ARM64 Raspberry Pi packaging")
    parser.add_argument("--mode", choices=("onedir", "onefile"), default="onedir")
    parser.add_argument("--check", action="store_true", help="Check dependencies without creating a bundle")
    args = parser.parse_args(argv)
    try:
        preflight()
        if args.check:
            print("Build preflight OK; no camera, GPIO or notifications were started.")
            return 0
        # 每次使用新目錄；不清空、刪除或覆蓋上一版成品與使用者設定。
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        prefix = f"posture_alarm_{args.mode}_{datetime.now():%Y%m%d_%H%M%S}_"
        work = Path(tempfile.mkdtemp(prefix=prefix, dir=build_root))
        destination = ROOT / "dist" / work.name
        destination.mkdir(parents=True, exist_ok=False)
        subprocess.run(build_command(args.mode, work, destination), cwd=ROOT, check=True)
        executable = destination / "posture_alarm"
        if args.mode == "onedir":
            executable /= "posture_alarm"
        if not executable.is_file():
            raise RuntimeError("Build finished without the expected executable; inspect the build output.")
        launcher = destination / "posture_alarm.desktop"
        launcher.write_text(desktop_entry(executable), encoding="utf-8")
        launcher.chmod(0o755)
        print(f"Executable: {executable}")
        print(f"Desktop launcher: {launcher}")
        print("Private demo.env, data and reports were NOT copied. See packaging_guide.md before use.")
        print("Next: run the executable with --self-test, then --preview, then test hardware on the Pi.")
        return 0
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Build stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
