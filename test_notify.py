"""Standalone LINE/Discord notification test script."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path


DEMO_ENV_PATH = Path(__file__).resolve().parent / "demo.env"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _post_line(message: str, timeout: float) -> bool:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    target = os.getenv("LINE_TARGET_ID", "").strip()
    if not token or not target:
        print("LINE: skipped, LINE_CHANNEL_ACCESS_TOKEN or LINE_TARGET_ID is empty")
        return False

    import requests

    response = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "to": target,
            "messages": [{"type": "text", "text": message}],
        },
        timeout=timeout,
    )
    print(f"LINE: HTTP {response.status_code}")
    if response.text:
        print(f"LINE response: {response.text[:500]}")
    return response.ok


def _post_discord(message: str, timeout: float) -> bool:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("Discord: skipped, DISCORD_WEBHOOK_URL is empty")
        return False

    import requests

    response = requests.post(webhook_url, json={"content": message}, timeout=timeout)
    print(f"Discord: HTTP {response.status_code}")
    if response.text:
        print(f"Discord response: {response.text[:500]}")
    return response.ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a test message to LINE and Discord.")
    parser.add_argument("--env-file", type=Path, default=DEMO_ENV_PATH, help="Path to env file, defaults to demo.env")
    parser.add_argument("--message", default="Posture Alarm test message", help="Message to send")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    _load_env_file(args.env_file)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"{args.message} ({timestamp})"

    print(f"Using env file: {args.env_file}")
    print("Sending test notifications...")
    line_ok = _post_line(message, args.timeout)
    discord_ok = _post_discord(message, args.timeout)
    print(f"Result: line={line_ok} discord={discord_ok}")

    if not line_ok or not discord_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
