import uuid
from types import SimpleNamespace

import pytest

from app.workers import tasks


class RetryScheduled(Exception):
    pass


class RetryTask:
    def __init__(self, retries: int = 0):
        self.request = SimpleNamespace(retries=retries)
        self.calls: list[dict] = []

    def retry(self, **kwargs):
        self.calls.append(kwargs)
        raise RetryScheduled()


def test_retryable_telegram_notification_uses_bounded_exponential_backoff():
    task = RetryTask(retries=2)
    error = tasks.tg.TelegramError("Telegram is unavailable", 503)

    with pytest.raises(RetryScheduled):
        tasks._retry_notification_task(task, "new_application", "app-id", error)

    assert task.calls == [{"exc": error, "countdown": 120, "max_retries": 3}]


def test_telegram_rate_limit_honours_retry_after_with_a_safe_cap():
    task = RetryTask()
    error = tasks.tg.TelegramError("Too Many Requests", 429, retry_after=900)

    with pytest.raises(RetryScheduled):
        tasks._retry_notification_task(task, "candidate_status", "app-id", error)

    assert task.calls[0]["countdown"] == 300


def test_permanent_or_exhausted_telegram_notification_does_not_retry():
    permanent = RetryTask()
    assert (
        tasks._retry_notification_task(
            permanent,
            "new_application",
            "app-id",
            tasks.tg.TelegramError("Forbidden", 403),
        )
        == "failed: permanent Telegram error (403)"
    )
    assert permanent.calls == []

    exhausted = RetryTask(retries=3)
    assert (
        tasks._retry_notification_task(
            exhausted,
            "candidate_status",
            "app-id",
            tasks.tg.TelegramError("Service Unavailable", 503),
        )
        == "failed: retry limit exhausted"
    )
    assert exhausted.calls == []


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
        None,
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
        raise tasks.tg.TelegramError("Telegram cannot fetch the photo", 400)

    async def send_message(token, chat_id, text, **kwargs):
        sent.update(token=token, chat_id=chat_id, text=text, kwargs=kwargs)

    monkeypatch.setattr(tasks.settings, "PLATFORM_BOT_TOKEN", "platform-token")
    monkeypatch.setattr(tasks.tg, "send_photo", failed_photo)
    monkeypatch.setattr(tasks.tg, "send_message", send_message)
    keyboard = {"inline_keyboard": [[{"text": "Открыть в панели", "url": "https://panel"}]]}

    await tasks._send_hr_application_notification(
        123,
        "👤 Кандидат: Азиза Каримова",
        None,
        "https://example.com/unreachable.jpg",
        keyboard,
    )

    assert sent["text"] == "👤 Кандидат: Азиза Каримова"
    assert sent["kwargs"]["reply_markup"] == keyboard


@pytest.mark.asyncio
async def test_hr_notification_rethrows_temporary_photo_delivery_failure(monkeypatch):
    async def failed_photo(*args, **kwargs):
        raise tasks.tg.TelegramError("Telegram unavailable", 503)

    monkeypatch.setattr(tasks.tg, "send_photo", failed_photo)

    with pytest.raises(tasks.tg.TelegramError, match="unavailable"):
        await tasks._send_hr_application_notification(
            123,
            "👤 Кандидат: Азиза Каримова",
            None,
            "https://example.com/portrait.jpg",
            None,
        )


def test_only_company_wide_answers_are_rendered_for_group_notification():
    text = tasks._common_answers_text(
        [
            {
                "question_id": "common",
                "question_text": "<b>Опыт</b>?",
                "answer": "3 года",
                "is_common": True,
                "skipped": False,
            },
            {
                "question_id": "vacancy",
                "question_text": "Почему эта вакансия?",
                "answer": "Интересно",
                "is_common": False,
                "skipped": False,
            },
            {
                "question_id": "photo",
                "question_text": "Фото",
                "answer": "portrait.jpg",
                "is_common": True,
                "profile_field": "candidate_photo",
                "skipped": False,
            },
        ],
        set(),
    )

    assert text is not None
    assert "Опыт?" in text
    assert "3 года" in text
    assert "Почему эта вакансия" not in text
    assert "portrait.jpg" not in text


@pytest.mark.asyncio
async def test_long_common_answers_follow_photo_in_separate_message(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def send_photo(token, chat_id, photo, caption, **kwargs):
        calls.append(("photo", caption))

    async def send_message(token, chat_id, text, **kwargs):
        calls.append(("message", text))

    monkeypatch.setattr(tasks.settings, "PLATFORM_BOT_TOKEN", "platform-token")
    monkeypatch.setattr(tasks.tg, "send_photo", send_photo)
    monkeypatch.setattr(tasks.tg, "send_message", send_message)

    await tasks._send_hr_application_notification(
        -100123,
        "🔔 <b>Новая заявка</b>",
        "📝 <b>Ответы</b>\n" + "A" * 1500,
        "https://example.com/portrait.jpg",
        None,
    )

    assert calls[0] == ("photo", "🔔 <b>Новая заявка</b>")
    assert calls[1][0] == "message"
    assert "Ответы" in calls[1][1]


def test_local_frontend_url_omits_button_without_suppressing_notification(monkeypatch):
    monkeypatch.setattr(tasks.settings, "FRONTEND_URL", "http://localhost:5173")

    assert tasks._panel_button(uuid.uuid4()) is None
