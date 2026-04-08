"""LINE Messaging API notifier."""

from __future__ import annotations

from typing import Any


class LineNotifier:
    def __init__(self, channel_access_token: str = "", to: str = "", timeout: float = 5.0) -> None:
        self.channel_access_token = channel_access_token
        self.to = to
        self.timeout = timeout

    def send(self, message: str) -> bool:
        if not self.channel_access_token or not self.to:
            return False
        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": self.to,
            "messages": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        }
        try:
            requests = self._load_requests()
            response = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            return bool(response.ok)
        except Exception:
            return False

    @staticmethod
    def _load_requests() -> Any:
        import requests

        return requests
