"""Bottom (reply) keyboards.

These drive the bot the way a real candidate does: every interaction is a tap, which
Telegram delivers as a plain text message, routed back to an action through the stored
label→action map. No callback payloads anywhere.
"""

import uuid

import pytest_asyncio
from aiogram.types import ReplyKeyboardMarkup
from sqlalchemy import select

from app.core.crypto import encrypt
from app.models import Application, ApplicationStatus, Branch, Company, Question, Vacancy
from app.models import Bot as BotModel
from tests.conftest import BOT_TOKEN, TestSession, tap, tap_matching
from tests.conftest import feed as _feed

# The main menu for the default fixture: one language, branch mode off — so no
# "📍 Филиалы" and no "🌐 Язык".
MENU_NO_BRANCHES = [
    "🏢 О компании",
    "📋 Вакансии",
    "📰 Новости",
    "☎️ Контакты / Адрес",
    "📨 Мои заявки",
]


def _markups(session):
    return [
        c.reply_markup
        for c in session.calls
        if getattr(c, "reply_markup", None) is not None
    ]


# --------------------------------------------------------------------------- shape


async def test_every_keyboard_is_a_bottom_keyboard(bot, session, tenant):
    """The whole point: nothing should render as buttons attached to a message."""
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")

    markups = _markups(session)
    assert markups, "expected at least one keyboard"
    for markup in markups:
        assert isinstance(markup, ReplyKeyboardMarkup), f"inline keyboard leaked: {markup}"
        assert markup.resize_keyboard is True


async def test_main_menu_is_shown_on_start(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    assert session.buttons == MENU_NO_BRANCHES


async def test_language_button_only_for_multilingual_companies(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    assert "🌐 Язык" not in session.buttons


# --------------------------------------------------------------------------- browsing


async def test_browse_and_open_a_vacancy_by_tapping(bot, session, tenant):
    await _feed(bot, tenant, text="/start")

    await tap(bot, tenant, "📋 Вакансии")
    assert "Бариста" in session.buttons

    session.clear()
    await tap(bot, tenant, "Бариста")
    assert "Бариста" in session.last_text
    assert "Хорошая работа" in session.last_text
    assert "✅ Откликнуться" in session.buttons


async def test_main_menu_button_returns_home(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")

    session.clear()
    await tap(bot, tenant, "🏠 Главное меню")
    assert session.buttons == MENU_NO_BRANCHES


async def test_stale_button_from_an_earlier_screen_is_ignored(bot, session, tenant):
    """Reply keyboards linger on screen, so only the current one may be activated."""
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")  # keyboard is now the vacancy card

    session.clear()
    # "Бариста" belonged to the previous keyboard and must no longer route anywhere.
    await tap(bot, tenant, "Бариста")
    assert "Выберите раздел" in session.last_text


async def test_menu_labels_survive_a_lost_map(bot, session, tenant):
    """Redis eviction must not brick a keyboard Telegram is still showing."""
    from app.core.redis_client import get_redis

    await _feed(bot, tenant, text="/start")
    redis = get_redis()
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()

    session.clear()
    await tap(bot, tenant, "📋 Вакансии")
    assert "Выберите вакансию" in session.last_text


async def test_unknown_text_redraws_the_menu(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    session.clear()
    await tap(bot, tenant, "что-то непонятное")
    assert "Выберите раздел" in session.last_text
    assert "📋 Вакансии" in session.buttons


# --------------------------------------------------------------------------- branches


@pytest_asyncio.fixture
async def branch_tenant():
    """Two branches, each with one active vacancy, branch mode on."""
    async with TestSession() as db:
        company = Company(
            name="Acme",
            slug=f"acme-{uuid.uuid4().hex[:6]}",
            branches_enabled=True,
            enabled_languages=["ru"],
        )
        db.add(company)
        await db.flush()

        bot_row = BotModel(
            company_id=company.id,
            token_encrypted=encrypt(BOT_TOKEN),
            bot_username="acme_hr_bot",
            webhook_secret="s3cret",
        )
        chilanzar = Branch(company_id=company.id, name="Чиланзар", city="Ташкент", sort_order=0)
        yunusabad = Branch(company_id=company.id, name="Юнусабад", city="Ташкент", sort_order=1)
        db.add_all([bot_row, chilanzar, yunusabad])
        await db.flush()

        db.add_all(
            [
                Vacancy(
                    company_id=company.id, branch_id=chilanzar.id,
                    title="Бариста", status="active", sort_order=0,
                ),
                Vacancy(
                    company_id=company.id, branch_id=yunusabad.id,
                    title="Кассир", status="active", sort_order=1,
                ),
            ]
        )
        await db.commit()
        return {"company_id": company.id, "bot_id": bot_row.id}


async def test_branch_then_vacancy_by_tapping(bot, session, branch_tenant):
    await _feed(bot, branch_tenant, text="/start")

    await tap(bot, branch_tenant, "📋 Вакансии")
    assert "Выберите филиал" in session.last_text
    assert any("Чиланзар" in b for b in session.buttons)

    # Read the label off the live keyboard before clearing — `buttons` reads the recorded
    # calls, so clearing first would leave nothing to match against.
    await tap_matching(bot, branch_tenant, session, "Чиланзар")
    assert "Бариста" in session.buttons
    assert "⬅️ К филиалам" in session.buttons

    session.clear()
    await tap(bot, branch_tenant, "⬅️ К филиалам")
    assert "Выберите филиал" in session.last_text


async def test_branch_counter_is_on_the_button(bot, session, branch_tenant):
    await _feed(bot, branch_tenant, text="/start")
    await tap(bot, branch_tenant, "📋 Вакансии")
    assert any(b.startswith("📍 Чиланзар — Ташкент (1)") for b in session.buttons)


# --------------------------------------------------------------------------- the form


async def _add_questions(tenant, *questions):
    async with TestSession() as db:
        vacancy_id = tenant.get("vacancy_id")
        for order, q in enumerate(questions):
            db.add(
                Question(
                    company_id=tenant["company_id"],
                    vacancy_id=vacancy_id,
                    sort_order=order,
                    **q,
                )
            )
        await db.commit()


async def test_single_choice_answered_by_tapping(bot, session, tenant):
    await _add_questions(
        tenant, {"text": "Смена?", "type": "single_choice", "options": ["Утро", "Вечер"]}
    )
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")

    session.clear()
    await tap(bot, tenant, "✅ Откликнуться")
    assert "Смена?" in session.last_text
    assert session.buttons[:2] == ["Утро", "Вечер"]
    # Every form screen keeps a way out.
    assert "✖️ Отменить" in session.buttons

    session.clear()
    await tap(bot, tenant, "Вечер")
    assert "Проверьте ваши ответы" in session.last_text
    assert "✅ Отправить" in session.buttons

    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == "Вечер"


async def test_text_question_keeps_cancel_on_screen(bot, session, tenant):
    await _add_questions(tenant, {"text": "Как вас зовут?", "type": "short_text"})
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")

    session.clear()
    await tap(bot, tenant, "✅ Откликнуться")
    assert "Как вас зовут?" in session.last_text
    assert session.buttons == ["✖️ Отменить"]

    # A typed answer is not confused for a button.
    session.clear()
    await tap(bot, tenant, "Аскар")
    assert "Проверьте ваши ответы" in session.last_text
    assert "Аскар" in session.last_text


async def test_cancel_button_aborts_the_form(bot, session, tenant):
    await _add_questions(tenant, {"text": "Как вас зовут?", "type": "short_text"})
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    session.clear()
    await tap(bot, tenant, "✖️ Отменить")
    assert "отменено" in session.last_text
    assert "📋 Вакансии" in session.buttons

    async with TestSession() as db:
        assert await db.scalar(select(Application)) is None


async def test_optional_question_shows_a_skip_button(bot, session, tenant):
    await _add_questions(
        tenant, {"text": "Ссылка на резюме?", "type": "short_text", "is_required": False}
    )
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")

    session.clear()
    await tap(bot, tenant, "✅ Откликнуться")
    assert "⏭ Пропустить" in session.buttons

    await tap(bot, tenant, "⏭ Пропустить")
    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["skipped"] is True


async def test_multi_choice_redraws_checkmarks_on_each_tap(bot, session, tenant):
    """A reply keyboard cannot be edited in place, so the keyboard is re-sent."""
    await _add_questions(
        tenant,
        {"text": "Навыки?", "type": "multi_choice", "options": ["Кофе", "Касса", "Зал"]},
    )
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    assert session.buttons[:3] == ["▫️ Кофе", "▫️ Касса", "▫️ Зал"]

    session.clear()
    await tap(bot, tenant, "▫️ Кофе")
    assert session.buttons[:3] == ["✅ Кофе", "▫️ Касса", "▫️ Зал"]
    assert session.last_text == "Кофе"

    await tap(bot, tenant, "▫️ Зал")
    assert session.buttons[:3] == ["✅ Кофе", "▫️ Касса", "✅ Зал"]

    # Tapping a selected option clears it again.
    await tap(bot, tenant, "✅ Кофе")
    assert session.buttons[:3] == ["▫️ Кофе", "▫️ Касса", "✅ Зал"]

    await tap(bot, tenant, "✅ Готово")
    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == ["Зал"]


async def test_required_multi_choice_warns_instead_of_advancing(bot, session, tenant):
    await _add_questions(
        tenant, {"text": "Навыки?", "type": "multi_choice", "options": ["Кофе", "Касса"]}
    )
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    session.clear()
    await tap(bot, tenant, "✅ Готово")
    assert any("хотя бы один" in text for text in session.texts)

    async with TestSession() as db:
        assert await db.scalar(select(Application)) is None


async def test_restart_button_clears_previous_answers(bot, session, tenant):
    await _add_questions(
        tenant, {"text": "Смена?", "type": "single_choice", "options": ["Утро", "Вечер"]}
    )
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")
    await tap(bot, tenant, "Утро")

    session.clear()
    await tap(bot, tenant, "✏️ Заполнить заново")
    assert "Смена?" in session.last_text
    assert session.buttons[:2] == ["Утро", "Вечер"]

    await tap(bot, tenant, "Вечер")
    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == "Вечер"


async def test_duplicate_labels_stay_individually_tappable(bot, session, tenant):
    """Two vacancies can legitimately share a title; both buttons must still work."""
    async with TestSession() as db:
        db.add(
            Vacancy(
                company_id=tenant["company_id"],
                title="Бариста",  # same title as the fixture's vacancy
                description="Вторая точка",
                status="active",
                sort_order=1,
            )
        )
        await db.commit()

    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")

    labels = [b for b in session.buttons if b.startswith("Бариста")]
    assert len(labels) == 2
    assert labels[0] != labels[1], "duplicate labels must be disambiguated"

    session.clear()
    await tap(bot, tenant, labels[1])
    assert "Вторая точка" in session.last_text


async def test_candidate_language_choice_by_tapping(bot, session, multi_tenant):
    await _feed(bot, multi_tenant, text="/start")
    assert session.buttons[:2] == ["✅ Русский", "O‘zbekcha"]

    session.clear()
    await tap(bot, multi_tenant, "O‘zbekcha")
    assert "📋 Vakansiyalar" in session.buttons

    session.clear()
    await tap(bot, multi_tenant, "📋 Vakansiyalar")
    assert "Barista" in session.buttons


async def test_my_applications_reachable_by_tapping(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    session.clear()
    await tap(bot, tenant, "📨 Мои заявки")
    assert "Бариста" in session.last_text
    assert "Новая" in session.last_text
    assert "📋 Вакансии" in session.buttons


async def test_candidate_row_records_the_application(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
        assert application is not None
        app_status = await db.get(ApplicationStatus, application.status_id)
    assert app_status.system_key == "new"
