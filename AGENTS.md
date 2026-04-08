# AGENTS.md

## Purpose

This file is a repository-specific execution guide for coding agents working in `D:\posture_alarm`.
It documents the commands, validation flow, and coding conventions that are actually present in this repo.
Prefer this file over generic agent habits.

## Repository Snapshot

- Language: Python
- Test runner: `pytest`
- Dependency source: `requirements.txt`
- Entry point: `main.py`
- ROI utility: `mark_bed_roi.py`
- Service template: `posture_alarm.service`
- Main packages: `alert/`, `core/`, `sensors/`, `storage/`, `ui/`, `vision/`
- Test directory: `tests/`
- There is currently no `package.json`, `pyproject.toml`, `tox.ini`, `noxfile.py`, `Makefile`, or CI config in the repo root.
- There is currently no `.cursorrules`, no `.cursor/rules/`, and no `.github/copilot-instructions.md` in this workspace.

## Working Directory

- Run commands from the repository root: `D:\posture_alarm`
- Use workspace-relative imports and paths that already exist in the codebase.

## Install Commands

- Install dependencies: `pip install -r requirements.txt`
- Recommended test install path is the same command above; `pytest` is already listed in `requirements.txt`.

## Run Commands

- Start the main app: `python main.py`
- Open the bed ROI marker: `python mark_bed_roi.py`
- Mark ROI and then launch main app: `python mark_bed_roi.py --run-main`

## Test Commands

- Run the full test suite: `python -m pytest tests -q`
- Run with verbose names: `python -m pytest tests -v`
- Run one test file: `python -m pytest tests/test_state_machine.py -q`
- Run one test case by node id: `python -m pytest tests/test_state_machine.py::test_suspect_timeout_back_to_normal -q`
- Filter tests by substring: `python -m pytest tests -k sedentary -q`

## Build / Lint / Typecheck Status

- There is no dedicated build command in this repository.
- There is no configured linter command such as `ruff`, `flake8`, `pylint`, or `black`.
- There is no configured typecheck command such as `mypy` or `pyright`.
- Do not invent new mandatory tooling in routine edits unless the user explicitly asks for it.
- For small changes, use targeted tests plus the import-health check below as the closest equivalent to a build smoke test.

## Import-Health Check

Use this after changes that affect module wiring, imports, or optional dependency loading:

```bash
python -c "from vision.camera import Camera; from vision.person_detector import PersonDetector; from vision.pose_estimator import PoseEstimator; from vision.fall_classifier import FallClassifier; from core.state_machine import PostureStateMachine; from core.utils import setup_logger; from sensors.imu_mpu6050 import IMU_MPU6050; from alert.buzzer_led import BuzzerLED; from alert.notifier_line import LineNotifier; from alert.notifier_telegram import TelegramNotifier; from storage.db_sqlite import EventDB; from storage.reporter import Reporter; from ui.overlay import Overlay; print('All imports OK')"
```

## Validation Expectations

- For a small logic change, run the most specific impacted test file first.
- For a single behavior within a file, prefer a single test node id before rerunning the whole file.
- For changes touching shared logic or cross-module imports, run `python -m pytest tests -q`.
- For changes affecting wiring, startup, or optional imports, also run the import-health check.
- If a command cannot run because of missing hardware, GUI, or platform dependencies, say so explicitly in your handoff.

## Architecture Map

- `main.py`: main orchestration loop, signal handling, ROI marking, module wiring.
- `config.py`: all environment-driven configuration and repository-wide constants.
- `vision/`: camera access, person detection, pose estimation, fall classification.
- `core/`: reusable core logic such as the state machine and logging helpers.
- `sensors/`: IMU integration and hardware-facing sensor code.
- `alert/`: buzzer/LED and notifier integrations.
- `storage/`: SQLite persistence and report generation.
- `ui/`: OpenCV overlay drawing helpers.
- `tests/`: deterministic unit tests for state machine, fall classifier, and SQLite storage.

## Code Style Guidelines

### Imports

- Use `from __future__ import annotations` at the top of Python modules, matching the existing codebase.
- Group imports in this order: standard library, third-party, then local package imports.
- Prefer absolute imports from repo packages like `from core.state_machine import PostureStateMachine`.
- Keep import lists explicit; avoid wildcard imports.
- For optional runtime dependencies such as `cv2`, `numpy`, `picamera2`, or `requests`, follow the existing lazy-import pattern inside helper methods when appropriate.

### Formatting

- Use 4-space indentation.
- Use double quotes consistently.
- Keep module docstrings short and descriptive.
- Break long constructor calls and conditionals across multiple lines with trailing commas.
- Prefer readable multi-line boolean expressions over compressed one-liners.
- Keep comments sparse; add them only when they explain a non-obvious compatibility or runtime detail.

### Types

- Add type annotations to public functions, methods, and important locals when it improves clarity.
- Prefer built-in generic syntax like `list[dict[str, float]]`, `tuple[float, float]`, and `dict[str, Any]`.
- Use `dataclass` for small structured result containers when the code already models data that way.
- Use `Enum` subclasses for finite state sets, matching `PostureState`.
- Use `Any` only at dynamic library boundaries or image/frame interfaces where concrete types are impractical.
- Do not introduce `Any` where the repo already has a simple precise type.

### Naming

- Modules and functions use `snake_case`.
- Classes use `PascalCase`.
- Constants use `UPPER_SNAKE_CASE`, especially in `config.py`.
- Internal helper functions may be prefixed with `_`.
- Tests use `test_...` names that describe the behavioral path being asserted.
- State values are uppercase strings such as `NORMAL`, `SUSPECT_FALL`, `FALLEN`, and `SEDENTARY`.

### Control Flow and Design

- Keep configuration parsing centralized in `config.py`; do not scatter new `os.getenv()` calls across unrelated modules.
- Pass config values into class constructors from `main.py` rather than hardcoding thresholds deep in feature code.
- Keep hardware, network, and GUI boundaries isolated behind small classes such as `Camera`, notifier classes, and `Overlay`.
- Prefer small helper methods for calculations, as seen in `FallClassifier` and `Camera`.
- Preserve simulation-friendly defaults; this repo is designed to run without requiring all hardware to be present.

### Error Handling

- Follow the repository's fail-soft approach at optional integration boundaries.
- For optional notifiers or unavailable backends, returning `False` is an established pattern.
- For required dynamic dependencies, raise a clear `RuntimeError` and chain the original exception with `from exc`.
- Do not swallow exceptions silently in core logic where a failure should be actionable.
- When broad `except Exception` is necessary at I/O or hardware boundaries, keep the protected block small.

### Logging

- Reuse `core.utils.setup_logger()` for console logging behavior.
- Prefer structured logger calls with format placeholders rather than string concatenation.
- Keep startup, shutdown, and operator-facing events loggable from the orchestration layer.

### Data and Persistence

- Keep event payloads JSON-serializable.
- Preserve SQLite schema compatibility unless the task explicitly includes a migration.
- Create parent directories with `Path(...).parent.mkdir(parents=True, exist_ok=True)` when introducing new local storage files.

### Tests

- Keep tests deterministic and hardware-free.
- Prefer injected timestamps over `sleep()` when testing state transitions or classifier windows.
- Use `:memory:` SQLite databases in tests when persistence behavior is the only concern.
- Add or update the narrowest relevant tests when changing logic in `core/`, `vision/`, or `storage/`.

## Change Boundaries

- Do not rename top-level modules or public classes unless the task requires it and all imports are updated.
- Do not add new dependencies casually; this repo is intentionally lightweight.
- Do not make tests depend on a real camera, GPIO, GUI, or network service.
- Do not move environment-variable parsing out of `config.py`.
- Do not replace the existing rule-based fall pipeline with a different architecture unless explicitly requested.

## Agent Reporting Expectations

When you finish a change, report:

- which files changed,
- which validation commands you ran,
- which validation commands you could not run,
- and any hardware/platform caveats that still matter.

## Practical Defaults For Agents

- Read `config.py`, the directly affected module, and the matching test file before editing.
- Match existing local patterns before introducing new abstractions.
- Prefer minimal diffs for bug fixes.
- If no lint or typecheck tool exists, do not claim linting or type safety was verified.
- If a requested validation is impossible in the current environment, state the exact blocker instead of guessing.
