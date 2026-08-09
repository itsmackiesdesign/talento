"""All candidate-facing bot handlers.

Every handler receives the per-update tenant context (``ctx``), a database session, a Redis
client and the resolved ``lang`` — injected by the webhook via ``dp.feed_update(...)`` and
the language middleware. Handlers never reach for a global session, which is what keeps one
tenant's update from touching another's data.

**Buttons are bottom (reply) keyboards, not inline.** A tap therefore arrives as an ordinary
text message, which ``app/bot/menu.py`` maps back to an action string. Everything funnels
into ``_dispatch_action`` so there is exactly one implementation per action; the
``callback_query`` handler at the bottom routes into the same place, so inline keyboards
still sitting in older chats keep working.
"""

import asyncio
import uuid
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import fsm, keyboards, menu
from app.bot.forms import (
    ValidationError,
    build_answers_payload,
    collect_questions,
    datetime_example,
    datetime_format_spec,
    get_system_status,
    render_summary,
    render_vacancy_card,
    validate_text_answer,
)
from app.bot.markup import to_telegram_html
from app.bot.runtime import BotContext
from app.bot.texts import t
from app.core.config import settings
from app.core.i18n import localized
from app.core.logging import get_logger
from app.models import (
    Application,
    ApplicationStatus,
    ApplicationStatusHistory,
    Branch,
    Candidate,
    News,
    Vacancy,
)
from app.services import telegram as tg
from app.services.storage import save_candidate_file

router = Router(name="candidate")
log = get_logger(__name__)


# --------------------------------------------------------------------------- plumbing


def _hex_to_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


def _multilingual(ctx: BotContext) -> bool:
    return len(ctx.company.enabled_languages or []) > 1


def _main_menu(ctx: BotContext, lang: str):
    """The main menu, with sections this company does not use left out."""
    return keyboards.main_menu(
        lang, multilingual=_multilingual(ctx), branches=bool(ctx.company.branches_enabled)
    )


async def _send_menu(
    message: Message,
    redis: Redis,
    ctx: BotContext,
    tg_user_id: int,
    text: str,
    keyboard: tuple,
) -> None:
    """Send a message with a bottom keyboard and record its label→action map.

    The map is replaced, not merged, so only the keyboard currently on screen can be
    activated — scrolling up and tapping a stale button does nothing.
    """
    markup, mapping = keyboard
    await message.answer(text, reply_markup=markup)
    await menu.remember(redis, ctx.bot_id, tg_user_id, mapping)


# --------------------------------------------------------------------------- screens


async def _active_vacancies(
    db: AsyncSession, company_id: uuid.UUID, branch_id: uuid.UUID | None, general: bool = False
) -> list[Vacancy]:
    stmt = select(Vacancy).where(Vacancy.company_id == company_id, Vacancy.status == "active")
    if general:
        stmt = stmt.where(Vacancy.branch_id.is_(None))
    elif branch_id is not None:
        stmt = stmt.where(Vacancy.branch_id == branch_id)
    return list((await db.scalars(stmt.order_by(Vacancy.sort_order, Vacancy.created_at))).all())


async def _branch_menu_items(db: AsyncSession, company_id: uuid.UUID, lang: str) -> list[tuple]:
    """Active branches that actually have openings, plus a 'general' bucket if needed."""
    counts = dict(
        (
            await db.execute(
                select(Vacancy.branch_id, func.count(Vacancy.id))
                .where(Vacancy.company_id == company_id, Vacancy.status == "active")
                .group_by(Vacancy.branch_id)
            )
        ).all()
    )
    branches = (
        await db.scalars(
            select(Branch)
            .where(Branch.company_id == company_id, Branch.is_active.is_(True))
            .order_by(Branch.sort_order, Branch.created_at)
        )
    ).all()

    items: list[tuple] = [
        (b.id, localized(b, "name", lang), localized(b, "city", lang), counts.get(b.id, 0))
        for b in branches
        if counts.get(b.id, 0) > 0
    ]
    if counts.get(None, 0) > 0:
        items.append((None, "general", None, counts[None]))
    return items


async def _show_main_menu(
    message: Message, redis: Redis, ctx: BotContext, tg_user_id: int, lang: str
) -> None:
    await _send_menu(
        message, redis, ctx, tg_user_id,
        t(lang, "menu_hint"),
        _main_menu(ctx, lang),
    )


async def _show_vacancy_list(
    message: Message,
    redis: Redis,
    db: AsyncSession,
    ctx: BotContext,
    tg_user_id: int,
    lang: str,
    scope: str,
    page: int = 0,
) -> None:
    """``scope`` is a branch id hex, 'general', or 'all' (branch mode off)."""
    if scope == "all":
        vacancies = await _active_vacancies(db, ctx.company_id, None)
        show_back = False
    elif scope == "general":
        vacancies = await _active_vacancies(db, ctx.company_id, None, general=True)
        show_back = True
    else:
        vacancies = await _active_vacancies(db, ctx.company_id, _hex_to_uuid(scope))
        show_back = True

    if not vacancies:
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "no_vacancies" if scope == "all" else "no_vacancies_branch"),
            _main_menu(ctx, lang),
        )
        return

    await _send_menu(
        message, redis, ctx, tg_user_id,
        t(lang, "choose_vacancy"),
        keyboards.vacancies_keyboard(
            [(v.id, localized(v, "title", lang)) for v in vacancies],
            page, scope, lang, show_back,
        ),
    )


async def _show_branches(
    message: Message,
    redis: Redis,
    db: AsyncSession,
    ctx: BotContext,
    tg_user_id: int,
    lang: str,
    page: int = 0,
) -> None:
    items = await _branch_menu_items(db, ctx.company_id, lang)
    if not items:
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "no_vacancies"),
            _main_menu(ctx, lang),
        )
        return
    # A single 'general' bucket and no real branches — skip the pointless extra tap.
    if len(items) == 1 and items[0][0] is None:
        await _show_vacancy_list(message, redis, db, ctx, tg_user_id, lang, "general")
        return
    await _send_menu(
        message, redis, ctx, tg_user_id,
        t(lang, "choose_branch"),
        keyboards.branches_keyboard(items, page, lang),
    )


async def _open_vacancies(
    message: Message, redis: Redis, db: AsyncSession, ctx: BotContext, tg_user_id: int, lang: str
) -> None:
    if ctx.company.branches_enabled:
        await _show_branches(message, redis, db, ctx, tg_user_id, lang)
    else:
        await _show_vacancy_list(message, redis, db, ctx, tg_user_id, lang, "all")


async def _show_vacancy_card(
    message: Message,
    redis: Redis,
    db: AsyncSession,
    ctx: BotContext,
    tg_user_id: int,
    lang: str,
    vacancy_id: uuid.UUID,
    scope: str | None = None,
) -> None:
    vacancy = await db.get(Vacancy, vacancy_id)
    # Tenant check: a deep link carries an id straight from the URL, so verify ownership
    # and publication status before rendering anything.
    if vacancy is None or vacancy.company_id != ctx.company_id or vacancy.status != "active":
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "vacancy_gone"),
            _main_menu(ctx, lang),
        )
        return

    branch = await db.get(Branch, vacancy.branch_id) if vacancy.branch_id else None
    if scope is None:
        if not ctx.company.branches_enabled:
            scope = "all"
        elif vacancy.branch_id:
            scope = vacancy.branch_id.hex
        else:
            scope = "general"

    card = render_vacancy_card(lang, vacancy, branch)
    if vacancy.photo_url:
        try:
            # Caption cap is 1024 chars; if the description overflows, fall back to sending
            # the photo and the full text separately rather than truncating the details.
            if len(card) <= 1024:
                await message.answer_photo(vacancy.photo_url, caption=card)
                card = None
            else:
                await message.answer_photo(vacancy.photo_url)
        except Exception as exc:  # noqa: BLE001 — a dead image must not hide the vacancy
            log.warning("vacancy_photo_failed", error=str(exc), vacancy_id=str(vacancy.id))

    await _send_menu(
        message, redis, ctx, tg_user_id,
        card if card is not None else t(lang, "apply_prompt"),
        keyboards.vacancy_card_keyboard(vacancy.id, scope, lang),
    )


async def _show_my_applications(
    message: Message, redis: Redis, db: AsyncSession, ctx: BotContext, tg_user_id: int, lang: str
) -> None:
    rows = (
        await db.execute(
            select(Application, Vacancy, ApplicationStatus)
            .join(Vacancy, Vacancy.id == Application.vacancy_id)
            .join(Candidate, Candidate.id == Application.candidate_id)
            .join(ApplicationStatus, ApplicationStatus.id == Application.status_id)
            .where(
                Application.company_id == ctx.company_id,
                Candidate.telegram_user_id == tg_user_id,
            )
            .order_by(Application.created_at.desc())
            .limit(20)
        )
    ).all()

    if not rows:
        text = t(lang, "no_applications")
    else:
        lines = [f"<b>{t(lang, 'my_apps_title')}</b>", ""]
        for app, vacancy, app_status in rows:
            lines.append(
                f"• <b>{escape(localized(vacancy, 'title', lang))}</b>\n"
                f"  {app.created_at:%d.%m.%Y} — {escape(localized(app_status, 'label', lang))}"
            )
        text = "\n".join(lines)

    await _send_menu(
        message, redis, ctx, tg_user_id, text,
        _main_menu(ctx, lang),
    )


async def _show_branch_directory(
    message: Message, redis: Redis, db: AsyncSession, ctx: BotContext, tg_user_id: int, lang: str
) -> None:
    """The standalone "📍 Branches" section — company locations, not a vacancy filter."""
    branches = (
        await db.scalars(
            select(Branch)
            .where(Branch.company_id == ctx.company_id, Branch.is_active.is_(True))
            .order_by(Branch.sort_order, Branch.created_at)
        )
    ).all()
    if not branches:
        await _send_menu(
            message, redis, ctx, tg_user_id, t(lang, "no_branches"), _main_menu(ctx, lang)
        )
        return

    await _send_menu(
        message, redis, ctx, tg_user_id,
        t(lang, "branches_list"),
        keyboards.branch_info_keyboard(
            [(b.id, localized(b, "name", lang), localized(b, "city", lang)) for b in branches],
            lang,
        ),
    )


async def _show_branch_card(
    message: Message,
    redis: Redis,
    db: AsyncSession,
    ctx: BotContext,
    tg_user_id: int,
    lang: str,
    branch_id: uuid.UUID,
) -> None:
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.company_id != ctx.company_id or not branch.is_active:
        await _show_branch_directory(message, redis, db, ctx, tg_user_id, lang)
        return

    name = localized(branch, "name", lang)
    city = localized(branch, "city", lang)
    address = localized(branch, "address", lang)

    lines = [f"🏢 <b>{escape(name)}</b>"]
    if city:
        lines.append(f"🌆 {escape(city)}")
    if address:
        lines.append(f"📍 {escape(address)}")
    caption = "\n".join(lines)

    if branch.photo_url:
        try:
            await message.answer_photo(branch.photo_url, caption=caption)
        except Exception as exc:  # noqa: BLE001 — a dead image URL must not hide the address
            log.warning("branch_photo_failed", error=str(exc), branch_id=str(branch.id))
            await message.answer(caption)
    else:
        await message.answer(caption)

    # Both coordinates are required together at the API level, so this is all-or-nothing.
    if branch.latitude is not None and branch.longitude is not None:
        await message.answer_location(latitude=branch.latitude, longitude=branch.longitude)

    await _send_menu(
        message, redis, ctx, tg_user_id,
        t(lang, "branches_list"),
        keyboards.branch_info_keyboard(
            [
                (b.id, localized(b, "name", lang), localized(b, "city", lang))
                for b in (
                    await db.scalars(
                        select(Branch)
                        .where(Branch.company_id == ctx.company_id, Branch.is_active.is_(True))
                        .order_by(Branch.sort_order, Branch.created_at)
                    )
                ).all()
            ],
            lang,
        ),
    )


NEWS_PAGE_SIZE = 5


async def _show_news(
    message: Message,
    redis: Redis,
    db: AsyncSession,
    ctx: BotContext,
    tg_user_id: int,
    lang: str,
    page: int = 0,
) -> None:
    """Paginated deliberately: sending an unbounded feed one message per item is the
    fastest way to hit Telegram's flood limits and get the bot throttled."""
    total = await db.scalar(
        select(func.count(News.id)).where(
            News.company_id == ctx.company_id, News.is_published.is_(True)
        )
    ) or 0
    if not total:
        await _send_menu(
            message, redis, ctx, tg_user_id, t(lang, "no_news"), _main_menu(ctx, lang)
        )
        return

    items = (
        await db.scalars(
            select(News)
            .where(News.company_id == ctx.company_id, News.is_published.is_(True))
            .order_by(News.sort_order, News.created_at.desc())
            .offset(page * NEWS_PAGE_SIZE)
            .limit(NEWS_PAGE_SIZE)
        )
    ).all()

    for item in items:
        title = localized(item, "title", lang)
        content = localized(item, "content", lang)
        body = f"<b>{escape(title)}</b>"
        if content:
            body += f"\n\n{to_telegram_html(content)}"
        if item.link_url:
            body += f"\n\n<a href=\"{escape(item.link_url)}\">{t(lang, 'read_more')}</a>"

        if item.photo_url:
            try:
                # Telegram caps photo captions at 1024 characters.
                await message.answer_photo(item.photo_url, caption=body[:1024])
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("news_photo_failed", error=str(exc), news_id=str(item.id))
        await message.answer(body)

    shown = page * NEWS_PAGE_SIZE + len(items)
    await _send_menu(
        message, redis, ctx, tg_user_id,
        t(lang, "news_title"),
        keyboards.news_keyboard(lang, has_more=shown < total, next_page=page + 1),
    )


async def _show_vacancy_entry(
    message: Message, redis: Redis, db: AsyncSession, ctx: BotContext, tg_user_id: int, lang: str
) -> None:
    """Entry point for "🧑🏻‍🍳 Vacancies".

    The 🔥/🌐 chooser only appears when both halves have something behind them; otherwise
    it would be a menu with a dead option, so we go straight to whichever one applies.
    """
    has_hot = (
        await db.scalar(
            select(Vacancy.id)
            .where(
                Vacancy.company_id == ctx.company_id,
                Vacancy.status == "active",
                Vacancy.is_hot.is_(True),
            )
            .limit(1)
        )
    ) is not None
    use_branches = bool(ctx.company.branches_enabled)

    if has_hot and use_branches:
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "vacancies_menu"),
            keyboards.vacancy_types_keyboard(lang, show_hot=True, show_branches=True),
        )
    elif use_branches:
        await _show_branches(message, redis, db, ctx, tg_user_id, lang)
    else:
        await _show_vacancy_list(message, redis, db, ctx, tg_user_id, lang, "all")


async def _show_hot_vacancies(
    message: Message, redis: Redis, db: AsyncSession, ctx: BotContext, tg_user_id: int, lang: str
) -> None:
    vacancies = list(
        (
            await db.scalars(
                select(Vacancy)
                .where(
                    Vacancy.company_id == ctx.company_id,
                    Vacancy.status == "active",
                    Vacancy.is_hot.is_(True),
                )
                .order_by(Vacancy.sort_order, Vacancy.created_at)
            )
        ).all()
    )
    if not vacancies:
        await _send_menu(
            message, redis, ctx, tg_user_id, t(lang, "no_hot_vacancies"), _main_menu(ctx, lang)
        )
        return

    await _send_menu(
        message, redis, ctx, tg_user_id,
        t(lang, "hot_vacancies_title"),
        keyboards.vacancies_keyboard(
            [(v.id, localized(v, "title", lang)) for v in vacancies], 0, "hot", lang, False
        ),
    )


# --------------------------------------------------------------------------- the form


def _form_lang(state: fsm.FormState, fallback: str) -> str:
    """The language the form was started in — see ``_start_application``."""
    return state.lang or fallback


async def _ask_current(
    message: Message,
    redis: Redis,
    ctx: BotContext,
    tg_user_id: int,
    state: fsm.FormState,
    lang: str,
) -> None:
    question = state.current
    if question is None:
        return
    lang = _form_lang(state, lang)
    # question.text is already Telegram HTML (converted once in collect_questions), so it
    # is sent as-is: no escaping (that would print literal tags) and no longer wrapped in a
    # forced <b> — the HR now controls emphasis themselves via the toolbar.
    body = question.text
    optional = not question.is_required

    if question.type == "datetime":
        # The mask is invisible otherwise — without this hint a candidate has no way to
        # know whether "8/2/99" is an acceptable answer, so every attempt would fail the
        # regex before they ever see MM.DD.YYYY spelled out.
        mask = (question.validation or {}).get("mask", "date")
        hint = t(
            lang,
            "datetime_hint",
            format=datetime_format_spec(mask),
            example=datetime_example(mask),
        )
        body = f"{body}\n\n<i>{hint}</i>"

    if question.type == "single_choice":
        keyboard = keyboards.single_choice_keyboard(question.options or [], lang, optional)
    elif question.type == "multi_choice":
        keyboard = keyboards.multi_choice_keyboard(
            question.options or [], state.pending, lang, optional
        )
    elif question.type == "phone":
        keyboard = keyboards.phone_keyboard(lang, optional)
    else:
        keyboard = keyboards.text_answer_keyboard(lang, optional)

    await _send_menu(message, redis, ctx, tg_user_id, body, keyboard)


async def _store_answer(
    message: Message,
    ctx: BotContext,
    redis: Redis,
    state: fsm.FormState,
    lang: str,
    tg_user_id: int,
    value,
    display=None,
    raw=None,
    skipped: bool = False,
) -> None:
    """Record the answer to the current question and advance, or move to confirmation.

    ``value`` is the base-language value stored in the application; ``display`` is what the
    candidate actually saw and is echoed back in the summary.
    """
    question = state.current
    if question is None:
        return
    lang = _form_lang(state, lang)
    state.answers[question.id] = {
        "value": value,
        "display": display if display is not None else value,
        "raw": raw,
        "skipped": skipped,
    }
    state.pending = []
    state.current_index += 1

    if state.current_index >= state.total:
        state.state = fsm.STATE_CONFIRMING
        await fsm.save(redis, ctx.bot_id, tg_user_id, state)
        await _send_menu(
            message, redis, ctx, tg_user_id,
            render_summary(lang, state.questions, state.answers),
            keyboards.confirm_keyboard(lang),
        )
        return

    await fsm.save(redis, ctx.bot_id, tg_user_id, state)
    await _ask_current(message, redis, ctx, tg_user_id, state, lang)


async def _start_application(
    message: Message,
    redis: Redis,
    db: AsyncSession,
    ctx: BotContext,
    tg_user_id: int,
    tg_user,
    lang: str,
    vacancy_id: uuid.UUID,
) -> None:
    vacancy = await db.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.company_id != ctx.company_id or vacancy.status != "active":
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "vacancy_gone"),
            _main_menu(ctx, lang),
        )
        return

    existing_row = (
        await db.execute(
            select(Application, ApplicationStatus)
            .join(Candidate, Candidate.id == Application.candidate_id)
            .join(ApplicationStatus, ApplicationStatus.id == Application.status_id)
            .where(
                Application.vacancy_id == vacancy_id,
                Candidate.telegram_user_id == tg_user_id,
            )
        )
    ).first()
    if existing_row is not None:
        _existing, existing_status = existing_row
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "already_applied", status=escape(localized(existing_status, "label", lang))),
            _main_menu(ctx, lang),
        )
        return

    # Questions are snapshotted in the language the candidate is using right now. Switching
    # language mid-form would be confusing, so the snapshot keeps the form coherent even if
    # they change it afterwards.
    questions = await collect_questions(db, ctx.company_id, vacancy_id, lang)
    if not questions:
        # No form configured — the tap itself is the application.
        await _create_application(message, ctx, db, redis, lang, vacancy, [], {}, tg_user)
        return

    state = fsm.FormState(vacancy_id=vacancy_id.hex, questions=questions, lang=lang)
    await fsm.save(redis, ctx.bot_id, tg_user_id, state)
    await message.answer(t(lang, "form_start"))
    await _ask_current(message, redis, ctx, tg_user_id, state, lang)


async def _create_application(
    message: Message,
    ctx: BotContext,
    db: AsyncSession,
    redis: Redis,
    lang: str,
    vacancy: Vacancy,
    questions: list,
    answers: dict,
    tg_user,
) -> None:
    candidate = await db.scalar(
        select(Candidate).where(Candidate.telegram_user_id == tg_user.id)
    )
    if candidate is None:
        candidate = Candidate(
            telegram_user_id=tg_user.id,
            telegram_username=tg_user.username,
            first_name=tg_user.first_name or "",
            language=lang,
        )
        db.add(candidate)
        await db.flush()
    else:
        candidate.telegram_username = tg_user.username
        candidate.first_name = tg_user.first_name or candidate.first_name
        candidate.language = lang

    # Promote the first phone answer onto the candidate so HR sees it without opening the form.
    payload = build_answers_payload(questions, answers)
    for item in payload:
        if item["type"] == "phone" and item["answer"]:
            candidate.phone = item["answer"]
            break

    new_status = await get_system_status(db, ctx.company_id, "new")
    application = Application(
        company_id=ctx.company_id,
        vacancy_id=vacancy.id,
        candidate_id=candidate.id,
        status_id=new_status.id,
        answers=payload,
    )
    db.add(application)
    try:
        await db.flush()
    except Exception:
        # Lost a race against the UNIQUE(vacancy_id, candidate_id) constraint — the
        # candidate double-tapped Submit. Treat the first write as authoritative.
        await db.rollback()
        await fsm.clear(redis, ctx.bot_id, tg_user.id)
        await _send_menu(
            message, redis, ctx, tg_user.id,
            t(lang, "already_applied", status=escape(localized(new_status, "label", lang))),
            _main_menu(ctx, lang),
        )
        return

    db.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status_id=None,
            to_status_id=new_status.id,
            from_status_label=None,
            # Base language — history is HR-facing, same convention as vacancy titles in
            # the panel: shown as authored, never re-translated per viewer.
            to_status_label=new_status.label,
        )
    )
    await db.commit()
    await fsm.clear(redis, ctx.bot_id, tg_user.id)

    await _send_menu(
        message, redis, ctx, tg_user.id,
        to_telegram_html(localized(ctx.bot_row, "after_apply_message", lang))
        or t(lang, "after_apply_default"),
        _main_menu(ctx, lang),
    )
    _enqueue_hr_notification(application.id)
    log.info(
        "application_created",
        application_id=str(application.id),
        company_id=str(ctx.company_id),
        vacancy_id=str(vacancy.id),
        lang=lang,
    )


def _enqueue_hr_notification(application_id: uuid.UUID) -> None:
    """Hand HR notification to Celery; a broker outage must never fail the candidate."""
    from app.workers.tasks import notify_new_application

    async def _send() -> None:
        try:
            await asyncio.to_thread(notify_new_application.delay, str(application_id))
        except Exception as exc:  # noqa: BLE001
            log.warning("notify_enqueue_failed", error=str(exc))

    asyncio.create_task(_send())  # noqa: RUF006


# --------------------------------------------------------------------------- dispatcher


async def _dispatch_action(
    action: str,
    message: Message,
    ctx: BotContext,
    db: AsyncSession,
    redis: Redis,
    lang: str,
    tg_user,
) -> None:
    """The single implementation of every button, whatever transport delivered it."""
    tg_user_id = tg_user.id

    if action == "menu":
        await _show_main_menu(message, redis, ctx, tg_user_id, lang)

    elif action == "vacancies":
        await _show_vacancy_entry(message, redis, db, ctx, tg_user_id, lang)

    elif action == "vac_hot":
        await _show_hot_vacancies(message, redis, db, ctx, tg_user_id, lang)

    elif action == "vac_branches":
        await _show_branches(message, redis, db, ctx, tg_user_id, lang)

    elif action == "branches":
        await _show_branch_directory(message, redis, db, ctx, tg_user_id, lang)

    elif action.startswith("binfo:"):
        branch_id = _hex_to_uuid(action.split(":", 1)[1])
        if branch_id:
            await _show_branch_card(message, redis, db, ctx, tg_user_id, lang, branch_id)

    elif action == "news":
        await _show_news(message, redis, db, ctx, tg_user_id, lang)

    elif action.startswith("newspage:"):
        await _show_news(
            message, redis, db, ctx, tg_user_id, lang, int(action.split(":", 1)[1] or 0)
        )

    elif action == "contacts":
        await _send_menu(
            message, redis, ctx, tg_user_id,
            to_telegram_html(localized(ctx.bot_row, "contacts_text", lang))
            or t(lang, "contacts_default"),
            _main_menu(ctx, lang),
        )

    elif action == "about":
        await _send_menu(
            message, redis, ctx, tg_user_id,
            to_telegram_html(localized(ctx.bot_row, "about_text", lang))
            or t(lang, "about_default"),
            _main_menu(ctx, lang),
        )

    elif action == "my_apps":
        await _show_my_applications(message, redis, db, ctx, tg_user_id, lang)

    elif action == "language":
        if _multilingual(ctx):
            await _send_menu(
                message, redis, ctx, tg_user_id,
                t(lang, "choose_language"),
                keyboards.language_keyboard(ctx.company.enabled_languages, lang, lang),
            )

    elif action.startswith("setlang:"):
        from app.bot import language

        chosen = action.split(":", 1)[1]
        # Only ever accept a language this company publishes — the label came from the
        # client and is not trustworthy.
        if chosen not in (ctx.company.enabled_languages or []):
            return
        await language.remember(redis, db, ctx.bot_id, tg_user_id, chosen)
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(chosen, "language_set"),
            _main_menu(ctx, chosen),
        )

    elif action == "back:branches":
        await _show_branches(message, redis, db, ctx, tg_user_id, lang)

    elif action.startswith("back:list:"):
        scope = action.split(":", 2)[2]
        if scope == "hot":
            await _show_hot_vacancies(message, redis, db, ctx, tg_user_id, lang)
        else:
            await _show_vacancy_list(message, redis, db, ctx, tg_user_id, lang, scope)

    elif action.startswith("brpage:"):
        await _show_branches(
            message, redis, db, ctx, tg_user_id, lang, int(action.split(":", 1)[1] or 0)
        )

    elif action.startswith("br:"):
        await _show_vacancy_list(
            message, redis, db, ctx, tg_user_id, lang, action.split(":", 1)[1]
        )

    elif action.startswith("page:"):
        _, scope, page = action.split(":", 2)
        await _show_vacancy_list(
            message, redis, db, ctx, tg_user_id, lang, scope, int(page or 0)
        )

    elif action.startswith("vac:"):
        parts = action.split(":", 2)
        vacancy_id = _hex_to_uuid(parts[1])
        # Scope is optional: deep links and older inline buttons omit it, and the card
        # falls back to inferring one from the vacancy's branch.
        scope = parts[2] if len(parts) > 2 else None
        if vacancy_id:
            await _show_vacancy_card(
                message, redis, db, ctx, tg_user_id, lang, vacancy_id, scope
            )

    elif action.startswith("apply:"):
        vacancy_id = _hex_to_uuid(action.split(":", 1)[1])
        if vacancy_id:
            await _start_application(
                message, redis, db, ctx, tg_user_id, tg_user, lang, vacancy_id
            )

    elif action == "cancel":
        await fsm.clear(redis, ctx.bot_id, tg_user_id)
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "cancelled"),
            _main_menu(ctx, lang),
        )

    else:
        await _dispatch_form_action(action, message, ctx, db, redis, lang, tg_user)


async def _dispatch_form_action(
    action: str,
    message: Message,
    ctx: BotContext,
    db: AsyncSession,
    redis: Redis,
    lang: str,
    tg_user,
) -> None:
    """Actions that only mean anything while a form is open."""
    tg_user_id = tg_user.id
    state = await fsm.load(redis, ctx.bot_id, tg_user_id)
    if state is None:
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "session_expired"),
            _main_menu(ctx, lang),
        )
        return
    form_lang = _form_lang(state, lang)

    if action.startswith("opt:"):
        if state.current is None or state.current.type != "single_choice":
            return
        options = state.current.options or []
        index = int(action.split(":", 1)[1])
        if not 0 <= index < len(options):
            return
        await _store_answer(
            message, ctx, redis, state, lang, tg_user_id,
            value=state.current.canonical_option(index),
            display=options[index],
        )

    elif action.startswith("mopt:"):
        if state.current is None or state.current.type != "multi_choice":
            return
        options = state.current.options or []
        index = int(action.split(":", 1)[1])
        if not 0 <= index < len(options):
            return
        # `pending` holds indexes, so a selection is language-independent.
        if index in state.pending:
            state.pending.remove(index)
        else:
            state.pending.append(index)
        await fsm.save(redis, ctx.bot_id, tg_user_id, state)
        # A reply keyboard cannot be edited in place, so redraw it with the new checkmarks.
        chosen = [options[i] for i in sorted(state.pending) if 0 <= i < len(options)]
        await _send_menu(
            message, redis, ctx, tg_user_id,
            ", ".join(chosen) if chosen else t(form_lang, "nothing_selected"),
            keyboards.multi_choice_keyboard(
                options, state.pending, form_lang, not state.current.is_required
            ),
        )

    elif action == "mdone":
        if state.current is None or state.current.type != "multi_choice":
            return
        if state.current.is_required and not state.pending:
            await message.answer(t(form_lang, "err_need_choice"))
            return
        question = state.current
        options = question.options or []
        chosen = sorted(state.pending)
        await _store_answer(
            message, ctx, redis, state, lang, tg_user_id,
            value=[question.canonical_option(i) for i in chosen],
            display=[options[i] for i in chosen if 0 <= i < len(options)],
        )

    elif action == "skip":
        if state.current is None:
            return
        if state.current.is_required:
            await message.answer(t(form_lang, "err_use_buttons"))
            return
        await _store_answer(
            message, ctx, redis, state, lang, tg_user_id, value=None, skipped=True
        )

    elif action == "restart":
        state.current_index = 0
        state.answers = {}
        state.pending = []
        state.state = fsm.STATE_FILLING
        await fsm.save(redis, ctx.bot_id, tg_user_id, state)
        await _ask_current(message, redis, ctx, tg_user_id, state, lang)

    elif action == "submit":
        vacancy = await db.get(Vacancy, uuid.UUID(state.vacancy_id))
        if vacancy is None or vacancy.company_id != ctx.company_id:
            # HR archived or deleted the vacancy while the candidate was filling the form.
            await fsm.clear(redis, ctx.bot_id, tg_user_id)
            await _send_menu(
                message, redis, ctx, tg_user_id,
                t(form_lang, "vacancy_gone"),
                _main_menu(ctx, form_lang),
            )
            return
        await _create_application(
            message, ctx, db, redis, form_lang, vacancy, state.questions, state.answers, tg_user
        )


# --------------------------------------------------------------------------- commands


async def _greet(message: Message, redis: Redis, ctx: BotContext, lang: str) -> None:
    await _send_menu(
        message, redis, ctx, message.from_user.id,
        to_telegram_html(localized(ctx.bot_row, "welcome_message", lang)) or t(lang, "welcome"),
        _main_menu(ctx, lang),
    )


@router.message(CommandStart(deep_link=True))
async def start_with_payload(
    message: Message,
    command: CommandObject,
    ctx: BotContext,
    db: AsyncSession,
    redis: Redis,
    lang: str,
) -> None:
    """Deep links from job ads and QR codes: ?start=vacancy_<hex> / branch_<hex>."""
    tg_user_id = message.from_user.id
    await fsm.clear(redis, ctx.bot_id, tg_user_id)
    payload = (command.args or "").strip()

    await _greet(message, redis, ctx, lang)

    if payload.startswith("vacancy_"):
        vid = _hex_to_uuid(payload.removeprefix("vacancy_"))
        if vid:
            await _show_vacancy_card(message, redis, db, ctx, tg_user_id, lang, vid)
            return
    elif payload.startswith("branch_"):
        bid = _hex_to_uuid(payload.removeprefix("branch_"))
        if bid:
            branch = await db.get(Branch, bid)
            if branch is not None and branch.company_id == ctx.company_id and branch.is_active:
                await _show_vacancy_list(
                    message, redis, db, ctx, tg_user_id, lang, bid.hex
                )
                return
    await _open_vacancies(message, redis, db, ctx, tg_user_id, lang)


@router.message(CommandStart())
async def start(
    message: Message, ctx: BotContext, db: AsyncSession, redis: Redis, lang: str
) -> None:
    tg_user_id = message.from_user.id
    await fsm.clear(redis, ctx.bot_id, tg_user_id)

    # First contact with a multilingual company: ask once, up front, rather than guessing
    # and making the candidate hunt for a way to switch.
    if _multilingual(ctx) and not await _has_chosen_language(redis, db, ctx, tg_user_id):
        await _send_menu(
            message, redis, ctx, tg_user_id,
            t(lang, "choose_language"),
            keyboards.language_keyboard(ctx.company.enabled_languages, lang, lang),
        )
        return

    await _greet(message, redis, ctx, lang)


async def _has_chosen_language(
    redis: Redis, db: AsyncSession, ctx: BotContext, tg_user_id: int
) -> bool:
    from app.bot import language

    try:
        if await redis.get(language._key(ctx.bot_id, tg_user_id)):
            return True
    except Exception:  # noqa: BLE001 — Redis trouble just means we ask again
        pass
    stored = await db.scalar(
        select(Candidate.language).where(Candidate.telegram_user_id == tg_user_id)
    )
    return bool(stored)


@router.message(Command("lang"))
async def change_language(
    message: Message, ctx: BotContext, db: AsyncSession, redis: Redis, lang: str
) -> None:
    await _dispatch_action("language", message, ctx, db, redis, lang, message.from_user)


@router.message(Command("cancel"))
async def cancel(
    message: Message, ctx: BotContext, db: AsyncSession, redis: Redis, lang: str
) -> None:
    await _dispatch_action("cancel", message, ctx, db, redis, lang, message.from_user)


@router.message(Command("menu"))
async def menu_command(
    message: Message, ctx: BotContext, db: AsyncSession, redis: Redis, lang: str
) -> None:
    await _dispatch_action("menu", message, ctx, db, redis, lang, message.from_user)


# --------------------------------------------------------------------------- input
# Contacts, documents and photos only ever arrive as answers, so they are matched before
# the generic text router below.


@router.message(F.contact)
async def on_contact(
    message: Message, ctx: BotContext, redis: Redis, lang: str
) -> None:
    state = await fsm.load(redis, ctx.bot_id, message.from_user.id)
    if state is None or state.current is None or state.current.type != "phone":
        return
    await _store_answer(
        message, ctx, redis, state, lang, message.from_user.id,
        value=message.contact.phone_number,
    )


@router.message(F.document | F.photo)
async def on_file(message: Message, ctx: BotContext, redis: Redis, lang: str) -> None:
    state = await fsm.load(redis, ctx.bot_id, message.from_user.id)
    if state is None or state.current is None:
        return
    question = state.current
    if question.type != "file":
        await message.answer(t(lang, "err_expect_text"))
        return

    if message.document:
        file_id, filename = message.document.file_id, message.document.file_name or "document"
        size = message.document.file_size or 0
        mime = message.document.mime_type or "application/octet-stream"
    else:
        largest = message.photo[-1]
        file_id, filename = largest.file_id, f"photo_{largest.file_unique_id}.jpg"
        size, mime = largest.file_size or 0, "image/jpeg"

    if size > settings.MAX_UPLOAD_BYTES:
        await message.answer(
            t(lang, "err_file_too_big", max=settings.MAX_UPLOAD_BYTES // (1024 * 1024))
        )
        return

    try:
        path = await tg.get_file_path(ctx.token, file_id)
        content = await tg.download_file(ctx.token, path)
    except Exception as exc:  # noqa: BLE001 — never strand the candidate on a CDN hiccup
        log.warning("file_download_failed", error=str(exc), bot_id=str(ctx.bot_id))
        await message.answer(t(lang, "generic_error"))
        return

    url = await save_candidate_file(ctx.company_id, content, filename, mime)
    await message.answer(t(lang, "file_received"))
    await _store_answer(
        message, ctx, redis, state, lang, message.from_user.id, value=filename, raw=url
    )


_STATIC_LABELS: dict[str, str] = {
    "menu_vacancies": "vacancies",
    "menu_about": "about",
    "menu_branches": "branches",
    "menu_news": "news",
    "menu_contacts": "contacts",
    "menu_my_apps": "my_apps",
    "menu_language": "language",
    "menu_back": "menu",
    "cancel_button": "cancel",
}


def _static_menu_action(text: str) -> str | None:
    """Match a main-menu label in any supported language, without consulting Redis."""
    from app.bot.texts import SUPPORTED

    for key, action in _STATIC_LABELS.items():
        if any(text == t(lang, key) for lang in SUPPORTED):
            return action
    return None


@router.message(F.text)
async def on_text(
    message: Message, ctx: BotContext, db: AsyncSession, redis: Redis, lang: str
) -> None:
    """A tap on a bottom keyboard, or a typed answer to an open form question.

    Resolution order matters. A tapped button is checked first, because a stray free-text
    answer that happens to read like a button is far rarer than the reverse — and while a
    form is open the stored map only contains that question's own buttons, so there is
    nothing else to collide with.
    """
    tg_user_id = message.from_user.id
    text = (message.text or "").strip()

    action = await menu.resolve(redis, ctx.bot_id, tg_user_id, text)
    if action:
        await _dispatch_action(action, message, ctx, db, redis, lang, message.from_user)
        return

    state = await fsm.load(redis, ctx.bot_id, tg_user_id)
    form_open = state is not None and state.state == fsm.STATE_FILLING

    # The main-menu labels are fixed strings we ship, so they can be recognised without the
    # stored map. That keeps the bot usable when Redis has been flushed or has expired the
    # map out from under a keyboard Telegram is still showing. Skipped while a form is open,
    # where an identical string is far more likely to be a genuine answer.
    if not form_open:
        static = _static_menu_action(text)
        if static:
            await _dispatch_action(static, message, ctx, db, redis, lang, message.from_user)
            return

    if state is not None and state.state == fsm.STATE_FILLING and state.current is not None:
        question = state.current
        form_lang = _form_lang(state, lang)
        if question.type in ("single_choice", "multi_choice"):
            await message.answer(t(form_lang, "err_use_buttons"))
            return
        if question.type == "file":
            await message.answer(t(form_lang, "err_need_file"))
            return
        try:
            value = validate_text_answer(question, text)
        except ValidationError as exc:
            await message.answer(t(form_lang, exc.key, **exc.kwargs))
            return
        await _store_answer(message, ctx, redis, state, lang, tg_user_id, value=value)
        return

    # Not a button and not an answer — the keyboard may be stale (Telegram keeps showing
    # it after a restart), so redraw the main menu rather than staying silent.
    await _show_main_menu(message, redis, ctx, tg_user_id, lang)


@router.callback_query()
async def on_callback(
    call: CallbackQuery, ctx: BotContext, db: AsyncSession, redis: Redis, lang: str
) -> None:
    """Compatibility path for inline keyboards still sitting in older chats.

    New keyboards are all bottom keyboards, but a candidate mid-conversation when this
    shipped would otherwise be left with dead buttons.
    """
    await call.answer()
    if not call.data or call.data == "noop":
        return
    await _dispatch_action(call.data, call.message, ctx, db, redis, lang, call.from_user)
