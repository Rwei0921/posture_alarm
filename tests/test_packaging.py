"""Frozen-entry and build-plan checks without PyInstaller, hardware or network."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

import build_rpi
import config
from core import runtime_paths
from core.control_process import MonitorProcess
import run_gui
from vision.camera import Camera


def test_source_paths_and_model_default_remain_unchanged():
    root = Path(__file__).resolve().parents[1]
    assert runtime_paths.application_root() == root
    assert runtime_paths.resource_root() == root
    with patch.dict(os.environ, {}, clear=True):
        importlib.reload(config)
        assert config.BASE_DIR == root
        assert config.POSE_MODEL_PATH == "models/pose_landmarker_lite.task"
    importlib.reload(config)


def test_frozen_config_separates_bundled_model_and_persistent_files(tmp_path):
    executable = tmp_path / "app" / "posture_alarm"
    resources = tmp_path / "temporary_bundle"
    try:
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "_MEIPASS", str(resources), create=True), \
                patch.object(sys, "executable", str(executable)), patch.dict(os.environ, {}, clear=True):
            importlib.reload(config)
            assert config.BASE_DIR == executable.parent
            assert Path(config.POSE_MODEL_PATH) == resources / "models" / "pose_landmarker_lite.task"
            assert Path(config.DB_PATH) == executable.parent / "data" / "events.db"
            assert config.REPORT_DIR == executable.parent / "reports"
            assert Path(config.LOG_FILE_PATH) == executable.parent / "data" / "posture_alarm.log"
        importlib.reload(config)
    finally:
        importlib.reload(config)


@pytest.mark.parametrize("mode", ["monitor", "camera", "alarm_test"])
def test_frozen_worker_relaunches_binary_without_python_script_arguments(tmp_path, mode):
    env_file = tmp_path / "demo.env"
    env_file.write_text("LINE_CHANNEL_ACCESS_TOKEN=dummy-secret\n", encoding="utf-8")
    controller = MonitorProcess(tmp_path, env_file)
    with patch.object(sys, "frozen", True, create=True), \
            patch("core.control_process.subprocess.Popen") as popen, \
            patch("core.control_process.threading.Thread"):
        controller.start(mode)
    command = popen.call_args.args[0]
    assert command == [sys.executable, "--worker", mode]
    assert "dummy-secret" not in str(command)
    assert popen.call_args.kwargs["env"]["LINE_CHANNEL_ACCESS_TOKEN"] == "dummy-secret"


def test_entry_dispatches_worker_without_creating_a_gui_or_reloading_settings():
    with patch("control_worker.worker", return_value=0) as worker, \
            patch("run_gui.launch") as gui, patch("run_gui.read_env") as settings:
        assert run_gui.main(["--worker", "alarm_test"]) == 0
    worker.assert_called_once_with("alarm_test")
    gui.assert_not_called()
    settings.assert_not_called()


def test_entry_retains_source_preview():
    with patch("run_gui.launch") as gui:
        assert run_gui.main(["--preview"]) == 0
    gui.assert_called_once_with(preview=True)


@pytest.mark.parametrize("original", [None, "", "/usr/lib/custom"])
def test_external_camera_environment_uses_system_libraries_only_when_frozen(original):
    environment = {"LD_LIBRARY_PATH": "/bundle/libs", "PATH": "/system/bin"}
    if original is not None:
        environment["LD_LIBRARY_PATH_ORIG"] = original
    with patch.dict(os.environ, environment, clear=True), \
            patch.object(sys, "platform", "linux"), patch.object(sys, "frozen", True, create=True):
        sanitized = runtime_paths.external_program_environment()
        assert sanitized.get("LD_LIBRARY_PATH") == original
        assert os.environ["LD_LIBRARY_PATH"] == "/bundle/libs"
        assert sanitized["PATH"] == "/system/bin"
    with patch.dict(os.environ, environment, clear=True), patch.object(sys, "frozen", False, create=True):
        assert runtime_paths.external_program_environment() == environment


def test_rpicam_receives_sanitized_environment_without_changing_its_command():
    camera = object.__new__(Camera)
    camera.width, camera.height, camera.rpicam_fps = 640, 480, 15
    camera._rpicam_buffer = bytearray()
    environment = {"PATH": "/system/bin"}
    with patch("vision.camera.external_program_environment", return_value=environment), \
            patch("vision.camera.subprocess.Popen") as popen:
        assert camera._open_rpicam(strict=True)
    assert popen.call_args.kwargs["env"] == environment
    assert popen.call_args.args[0][0] == "rpicam-vid"
    assert "640" in popen.call_args.args[0]


@pytest.mark.parametrize("mode", ["onedir", "onefile"])
def test_build_command_only_bundles_whitelisted_model_and_dependency_code(tmp_path, mode):
    with patch("build_rpi.importlib.util.find_spec", return_value=None):
        command = build_rpi.build_command(mode, tmp_path / "work", tmp_path / "dist")
    assert f"--{mode}" in command
    assert command[command.index("--add-data") + 1] == f"{build_rpi.ROOT / build_rpi.MODEL}:models"
    assert command[-1].endswith("run_gui.py")
    assert "fcntl" in command and "_lgpio" in command
    assert not any(private in part for private in ("demo.env", "data/", "reports/", "dummy-secret") for part in command)
    assert "--noconfirm" not in command


def test_preflight_rejects_windows_without_creating_artifacts_or_starting_build(tmp_path):
    with patch.object(build_rpi, "ROOT", tmp_path), patch.object(sys, "platform", "win32"), \
            patch("build_rpi.subprocess.run") as run:
        assert build_rpi.main([]) == 1
        assert list(tmp_path.iterdir()) == []
        run.assert_not_called()


def test_preflight_does_not_install_missing_tools_or_open_hardware():
    with patch.object(sys, "platform", "linux"), patch("build_rpi.platform.machine", return_value="aarch64"), \
            patch("build_rpi.importlib.util.find_spec", return_value=None), \
            patch("build_rpi.subprocess.run") as run:
        with pytest.raises(RuntimeError, match="requirements_build.txt"):
            build_rpi.preflight()
    run.assert_not_called()


def test_check_mode_never_builds_or_writes_output(tmp_path):
    with patch.object(build_rpi, "ROOT", tmp_path), patch("build_rpi.preflight"), \
            patch("build_rpi.subprocess.run") as run:
        assert build_rpi.main(["--check"]) == 0
        run.assert_not_called()
        assert list(tmp_path.iterdir()) == []


def test_self_test_does_not_initialize_devices_or_expose_exception_secrets(capsys):
    with patch("main.run") as monitor, patch("control_worker.worker") as worker, \
            patch("run_gui.importlib.import_module", side_effect=RuntimeError("dummy-secret")):
        assert run_gui.main(["--self-test"]) == 1
        monitor.assert_not_called()
        worker.assert_not_called()
    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "dummy-secret" not in output


def test_self_test_checks_imports_and_model_without_constructing_hardware():
    with patch("run_gui.importlib.import_module", return_value=Mock()), \
            patch("main.run") as monitor, patch("control_worker.worker") as worker:
        assert run_gui.main(["--self-test"]) == 0
        monitor.assert_not_called()
        worker.assert_not_called()


def test_real_source_entry_can_dispatch_and_stop_worker_from_another_directory(tmp_path):
    entry = Path(run_gui.__file__).resolve()
    result = subprocess.run(
        [sys.executable, "-u", str(entry), "--worker", "alarm_test"],
        input="stop\n", text=True, capture_output=True, cwd=tmp_path,
        env={**os.environ, "SIMULATE_GPIO": "1"}, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert '"phase": "stopped"' in result.stdout


def test_desktop_launcher_does_not_use_shell_or_change_autostart(tmp_path):
    entry = build_rpi.desktop_entry(tmp_path / "app with spaces" / "posture_alarm")
    assert 'Exec="' in entry and "Terminal=false" in entry
    assert "sh -c" not in entry and "autostart" not in entry
    assert "demo.env" not in entry


@pytest.mark.parametrize("mode", ["onedir", "onefile"])
def test_build_keeps_old_outputs_and_never_copies_runtime_settings(tmp_path, mode):
    old = tmp_path / "dist" / "old_release"
    old.mkdir(parents=True)
    settings = old / "demo.env"
    settings.write_text("LINE_TARGET_ID=dummy-existing\n", encoding="utf-8")

    def bundle(command, **_kwargs):
        destination = Path(command[command.index("--distpath") + 1])
        executable = destination / "posture_alarm"
        if mode == "onedir":
            executable.mkdir()
            executable /= "posture_alarm"
        executable.write_bytes(b"test-bundle-placeholder")

    with patch.object(build_rpi, "ROOT", tmp_path), patch("build_rpi.preflight"), \
            patch("build_rpi.importlib.util.find_spec", return_value=None), \
            patch("build_rpi.subprocess.run", side_effect=bundle):
        assert build_rpi.main(["--mode", mode]) == 0
    assert settings.read_text() == "LINE_TARGET_ID=dummy-existing\n"
    releases = [path for path in (tmp_path / "dist").iterdir() if path != old]
    assert len(releases) == 1
    assert (releases[0] / "posture_alarm.desktop").is_file()
    assert not list(releases[0].rglob("demo.env"))
