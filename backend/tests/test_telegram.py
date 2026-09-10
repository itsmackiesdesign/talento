import pytest

from app.services import telegram


@pytest.mark.asyncio
async def test_telegram_rate_limit_exposes_retry_after_for_workers(monkeypatch):
    class Response:
        status_code = 429

        @staticmethod
        def json():
            return {
                "ok": False,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 42},
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @staticmethod
        async def post(*args, **kwargs):
            return Response()

    monkeypatch.setattr(telegram.httpx, "AsyncClient", lambda **kwargs: Client())

    with pytest.raises(telegram.TelegramError) as exc_info:
        await telegram.call("test-token", "sendMessage", chat_id=1, text="Hello")

    assert exc_info.value.code == 429
    assert exc_info.value.retry_after == 42
    assert telegram.is_retryable(exc_info.value) is True
