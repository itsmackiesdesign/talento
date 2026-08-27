import uuid
from types import SimpleNamespace

import pytest

from app.workers import tasks


@pytest.mark.asyncio
async def test_worker_task_disposes_async_connections(monkeypatch):
    disposed = False

    async def dispose() -> None:
        nonlocal disposed
        disposed = True

    async def notification() -> str:
        return "sent"

    monkeypatch.setattr(tasks, "engine", SimpleNamespace(dispose=dispose))

    assert await tasks._run_with_fresh_db(notification()) == "sent"
    assert disposed is True


@pytest.mark.asyncio
async def test_worker_task_disposes_async_connections_after_failure(monkeypatch):
    disposed = False

    async def dispose() -> None:
        nonlocal disposed
        disposed = True

    async def notification() -> str:
        raise RuntimeError("delivery failed")

    monkeypatch.setattr(tasks, "engine", SimpleNamespace(dispose=dispose))

    with pytest.raises(RuntimeError, match="delivery failed"):
        await tasks._run_with_fresh_db(notification())
    assert disposed is True


@pytest.mark.asyncio
async def test_hr_notification_sends_candidate_photo_and_panel_button(monkeypatch):
    sent: dict = {}

    async def send_photo(token, chat_id, photo, caption, **kwargs):
        sent.update(
            token=token,
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            kwargs=kwargs,
        )

    async def unexpected_message(*args, **kwargs):
        raise AssertionError("text fallback should not be used")

    monkeypatch.setattr(tasks.settings, "PLATFORM_BOT_TOKEN", "platform-token")
    monkeypatch.setattr(tasks.settings, "FRONTEND_URL", "https://panel.example.com")
    monkeypatch.setattr(tasks.tg, "send_photo", send_photo)
    monkeypatch.setattr(tasks.tg, "send_message", unexpected_message)
    keyboard = tasks._panel_button(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    assert keyboard is not None

    await tasks._send_hr_application_notification(
        123,
        "👤 Кандидат: Азиза Каримова",
        "https://example.com/portrait.jpg",
        keyboard,
    )

    assert sent["photo"] == "https://example.com/portrait.jpg"
    assert sent["caption"] == "👤 Кандидат: Азиза Каримова"
    assert sent["kwargs"]["reply_markup"]["inline_keyboard"][0][0] == {
        "text": "Открыть в панели",
        "url": "https://panel.example.com/applications/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    }


@pytest.mark.asyncio
async def test_hr_notification_falls_back_to_text_when_photo_fails(monkeypatch):
    sent: dict = {}

    async def failed_photo(*args, **kwargs):
        raise tasks.tg.TelegramError("Telegram cannot fetch the photo")

    async def send_message(token, chat_id, text, **kwargs):
        sent.update(token=token, chat_id=chat_id, text=text, kwargs=kwargs)

    monkeypatch.setattr(tasks.settings, "PLATFORM_BOT_TOKEN", "platform-token")
    monkeypatch.setattr(tasks.tg, "send_photo", failed_photo)
    monkeypatch.setattr(tasks.tg, "send_message", send_message)
    keyboard = {"inline_keyboard": [[{"text": "Открыть в панели", "url": "https://panel"}]]}

    await tasks._send_hr_application_notification(
        123,
        "👤 Кандидат: Азиза Каримова",
        "https://example.com/unreachable.jpg",
        keyboard,
    )

    assert sent["text"] == "👤 Кандидат: Азиза Каримова"
    assert sent["kwargs"]["reply_markup"] == keyboard


def test_local_frontend_url_omits_button_without_suppressing_notification(monkeypatch):
    monkeypatch.setattr(tasks.settings, "FRONTEND_URL", "http://localhost:5173")

    assert tasks._panel_button(uuid.uuid4()) is None
