import importlib

import config


def test_line_channel_access_token_does_not_fallback_to_line_notify_token(monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("LINE_NOTIFY_TOKEN", "legacy-token")

    reloaded = importlib.reload(config)

    try:
        assert reloaded.LINE_CHANNEL_ACCESS_TOKEN == ""
    finally:
        importlib.reload(config)


def test_line_channel_access_token_uses_explicit_env(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "channel-token")

    reloaded = importlib.reload(config)

    try:
        assert reloaded.LINE_CHANNEL_ACCESS_TOKEN == "channel-token"
    finally:
        importlib.reload(config)
