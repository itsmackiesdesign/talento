"""Background tasks: notify HR of new applications, notify candidates of status changes.

Tasks are sync Celery functions that drive async I/O through ``asyncio.run``. Each task
owns its own event loop and session — nothing is shared with the web process.
"""

import asyncio
import uuid
from collections.abc import Coroutine
from html import escape
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select

from app.bot.texts import t
from app.core.config import settings
from app.core.crypto import decrypt
from app.core.db import SessionLocal, engine
from app.core.i18n import localized, normalise
from app.core.logging import get_logger
from app.models import (
    Application,
    ApplicationStatus,
    Bot,
    Branch,
    Candidate,
    Company,
    CompanyMember,
    User,
    Vacancy,
)
from app.services import telegram as tg
from app.services.candidate_profiles import resolve_candidate_profile
from app.workers.celery_app import celery_app

log = get_logger(__name__)


async def _run_with_fresh_db(coro: Coroutine[Any, Any, str]) -> str:
    """Run one Celery coroutine without carrying asyncpg connections to the next loop.

    Celery invokes each sync task separately and every invocation below uses
    ``asyncio.run()``, which creates a new event loop.  SQLAlchemy's async pool must be
    emptied before that loop closes or a later task can receive a connection tied to the
    previous loop.
    """
    try:
        return await coro
    finally:
        await engine.dispose()


@celery_app.task(name="talento.notify_new_application", max_retries=3, default_retry_delay=30)
def notify_new_application(application_id: str) -> str:
    return asyncio.run(_run_with_fresh_db(_notify_new_application(application_id)))


def _panel_button(application_id: uuid.UUID) -> dict[str, Any] | None:
    panel_url = f'{settings.FRONTEND_URL.rstrip("/")}/applications/{application_id}'
    parsed = urlparse(panel_url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname in {"localhost", "127.0.0.1", "::1"}:
        log.warning("hr_notify_panel_button_skipped", reason="frontend_url_is_not_public_https")
        return None
    return {
        "inline_keyboard": [[{"text": "Открыть в панели", "url": panel_url}]],
    }


async def _send_hr_application_notification(
    chat_id: int,
    text: str,
    photo_url: str | None,
    reply_markup: dict[str, Any] | None,
) -> None:
    if photo_url:
        try:
            await tg.send_photo(
                settings.PLATFORM_BOT_TOKEN,
                chat_id,
                photo_url,
                text,
                reply_markup=reply_markup,
            )
            return
        except tg.TelegramError as exc:
            # A local/private storage URL may not be reachable by Telegram. The HR should
            # still receive the application, so retry as text with the same panel button.
            log.warning(
                "hr_notify_photo_failed",
                chat_id=chat_id,
                photo_url=photo_url,
                error=exc.description,
            )

    await tg.send_message(
        settings.PLATFORM_BOT_TOKEN,
        chat_id,
        text,
        reply_markup=reply_markup,
    )


async def _notify_new_application(application_id: str) -> str:
    if not settings.PLATFORM_BOT_TOKEN:
        log.info("hr_notify_skipped", reason="no_platform_bot", application_id=application_id)
        return "skipped: PLATFORM_BOT_TOKEN not set"

    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(Application, Vacancy, Candidate, Company, Branch)
                .join(Vacancy, Vacancy.id == Application.vacancy_id)
                .join(Candidate, Candidate.id == Application.candidate_id)
                .join(Company, Company.id == Application.company_id)
                .outerjoin(Branch, Branch.id == Vacancy.branch_id)
                .where(Application.id == uuid.UUID(application_id))
            )
        ).first()
        if row is None:
            return "application not found"
        application, vacancy, candidate, company, branch = row

        recipients = (
            await db.scalars(
                select(User.telegram_user_id)
                .join(CompanyMember, CompanyMember.user_id == User.id)
                .where(
                    CompanyMember.company_id == company.id,
                    User.telegram_user_id.is_not(None),
                )
            )
        ).all()

    if not recipients:
        log.info("hr_notify_no_recipients", company_id=str(company.id))
        return "no linked recipients"

    profile = resolve_candidate_profile(application.answers, candidate.first_name)
    lines = ["🔔 <b>Новая заявка</b>", ""]
    if branch is not None:
        lines.append(f"🏢 Филиал: {escape(branch.name)}")
    lines.append(f"💼 Вакансия: {escape(vacancy.title)}")
    lines.append(f"👤 Кандидат: {escape(profile.name)}")
    if candidate.phone:
        lines.append(f"📞 Телефон: {escape(candidate.phone)}")
    if candidate.telegram_username:
        lines.append(f"✈️ Telegram: @{escape(candidate.telegram_username)}")
    text = "\n".join(lines)
    reply_markup = _panel_button(application.id)

    sent = 0
    for chat_id in recipients:
        try:
            await _send_hr_application_notification(
                chat_id,
                text,
                profile.photo_url,
                reply_markup,
            )
            sent += 1
        except tg.TelegramError as exc:
            # Most likely the HR blocked the bot; log and keep going for the rest of the team.
            log.warning("hr_notify_failed", chat_id=chat_id, error=exc.description)

    log.info("hr_notified", application_id=application_id, sent=sent)
    return f"sent to {sent}/{len(recipients)}"


@celery_app.task(name="talento.notify_candidate_status", max_retries=3, default_retry_delay=30)
def notify_candidate_status(application_id: str, from_status_id: str, to_status_id: str) -> str:
    return asyncio.run(
        _run_with_fresh_db(_notify_candidate_status(application_id, to_status_id))
    )


async def _notify_candidate_status(application_id: str, to_status_id: str) -> str:
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(Application, Vacancy, Candidate, Bot, ApplicationStatus)
                .join(Vacancy, Vacancy.id == Application.vacancy_id)
                .join(Candidate, Candidate.id == Application.candidate_id)
                .join(Bot, Bot.company_id == Application.company_id)
                .join(ApplicationStatus, ApplicationStatus.id == uuid.UUID(to_status_id))
                .where(Application.id == uuid.UUID(application_id))
            )
        ).first()
        if row is None:
            return "application or bot not found"
        _application, vacancy, candidate, bot, target_status = row

        # 'viewed'-style steps the HR flagged as not candidate-facing are the point of this
        # flag — see ApplicationStatus.notify_candidate.
        if not target_status.notify_candidate:
            return "status not notifiable"
        if not bot.notify_candidate_on_status or not bot.is_active:
            return "candidate notifications disabled"
        token = decrypt(bot.token_encrypted)
        # Write to the candidate in the language they applied in, not the bot's default.
        lang = normalise(candidate.language) or bot.language
        vacancy_title = localized(vacancy, "title", lang)
        status_text = localized(target_status, "label", lang)

    text = t(
        lang,
        "notify_status",
        vacancy=escape(vacancy_title),
        status=escape(status_text),
    )
    try:
        await tg.send_message(token, candidate.telegram_user_id, text)
    except tg.TelegramError as exc:
        log.warning(
            "candidate_notify_failed",
            application_id=application_id,
            error=exc.description,
        )
        return f"failed: {exc.description}"
    return "sent"
