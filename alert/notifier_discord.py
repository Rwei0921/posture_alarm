"""Discord webhook notifier."""

from __future__ import annotations

from typing import Any


class DiscordNotifier:
    def __init__(self, webhook_url: str = "", timeout: float = 5.0) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(self, message: str) -> bool:
        if not self.webhook_url:
            return False

        requests = self._load_requests()
        payload = {"content": message}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
            return bool(response.ok)
        except Exception:
            return False

    @staticmethod
    def _load_requests() -> Any:
        import requests

        return requests
