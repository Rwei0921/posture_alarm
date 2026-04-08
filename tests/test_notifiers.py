from alert.notifier_discord import DiscordNotifier
from alert.notifier_line import LineNotifier


class _FakeResponse:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok


class _FakeRequests:
    def __init__(self, ok: bool = True, should_raise: bool = False) -> None:
        self.ok = ok
        self.should_raise = should_raise
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.should_raise:
            raise RuntimeError("network error")
        return _FakeResponse(ok=self.ok)


def test_line_notifier_returns_false_when_unconfigured():
    notifier = LineNotifier()

    assert notifier.send("hello") is False


def test_line_notifier_posts_push_message_payload():
    fake_requests = _FakeRequests()
    notifier = LineNotifier(channel_access_token="token", to="U123")
    notifier._load_requests = lambda: fake_requests

    sent = notifier.send("姿勢警報：偵測到跌倒，時間：2026年04月09日 02:14:32")

    assert sent is True
    assert fake_requests.calls == [
        {
            "url": "https://api.line.me/v2/bot/message/push",
            "headers": {
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            "json": {
                "to": "U123",
                "messages": [{"type": "text", "text": "姿勢警報：偵測到跌倒，時間：2026年04月09日 02:14:32"}],
            },
            "timeout": 5.0,
        }
    ]


def test_line_notifier_returns_false_on_request_error():
    fake_requests = _FakeRequests(should_raise=True)
    notifier = LineNotifier(channel_access_token="token", to="U123")
    notifier._load_requests = lambda: fake_requests

    assert notifier.send("fall detected") is False


def test_line_notifier_returns_false_when_requests_is_missing():
    notifier = LineNotifier(channel_access_token="token", to="U123")
    notifier._load_requests = lambda: (_ for _ in ()).throw(ModuleNotFoundError("requests"))

    assert notifier.send("fall detected") is False


def test_discord_notifier_returns_false_when_unconfigured():
    notifier = DiscordNotifier()

    assert notifier.send("hello") is False


def test_discord_notifier_posts_webhook_payload():
    fake_requests = _FakeRequests()
    notifier = DiscordNotifier(webhook_url="https://discord.example/webhook")
    notifier._load_requests = lambda: fake_requests

    sent = notifier.send("姿勢警報：偵測到跌倒，時間：2026年04月09日 02:14:32")

    assert sent is True
    assert fake_requests.calls == [
        {
            "url": "https://discord.example/webhook",
            "json": {"content": "姿勢警報：偵測到跌倒，時間：2026年04月09日 02:14:32"},
            "timeout": 5.0,
        }
    ]


def test_discord_notifier_returns_false_on_request_error():
    fake_requests = _FakeRequests(should_raise=True)
    notifier = DiscordNotifier(webhook_url="https://discord.example/webhook")
    notifier._load_requests = lambda: fake_requests

    assert notifier.send("fall detected") is False


def test_discord_notifier_returns_false_when_requests_is_missing():
    notifier = DiscordNotifier(webhook_url="https://discord.example/webhook")
    notifier._load_requests = lambda: (_ for _ in ()).throw(ModuleNotFoundError("requests"))

    assert notifier.send("fall detected") is False
