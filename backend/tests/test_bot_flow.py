"""End-to-end candidate flow driven through the real aiogram Dispatcher.

Telegram itself is replaced by a fake session that records every outgoing call (see
``tests/conftest.py``), so the handlers, FSM, validation and persistence all run for real —
only the network is faked.
"""

from sqlalchemy import select

from app.models import Application, ApplicationStatus, Question, Vacancy
from tests.conftest import TestSession
from tests.conftest import feed as _feed

# Fixtures `bot`, `session` and `tenant` come from conftest.


async def _add_questions(tenant, *questions):
    async with TestSession() as db:
        for order, q in enumerate(questions):
            db.add(
                Question(
                    company_id=tenant["company_id"],
                    vacancy_id=tenant["vacancy_id"],
                    sort_order=order,
                    **q,
                )
            )
        await db.commit()


# --------------------------------------------------------------------------- tests


async def test_start_shows_welcome_and_menu(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    assert any("Здравствуйте" in text for text in session.texts)


async def test_vacancies_listed_without_branches(bot, session, tenant):
    await _feed(bot, tenant, text="📋 Вакансии")
    assert "Выберите вакансию" in session.last_text
    assert "Бариста" in session.buttons


async def test_vacancy_card_shows_details(bot, session, tenant):
    await _feed(bot, tenant, data=f"vac:{tenant['vacancy_id'].hex}")
    assert "Бариста" in session.last_text
    assert "Хорошая работа" in session.last_text


async def test_deep_link_opens_vacancy_card(bot, session, tenant):
    await _feed(bot, tenant, text=f"/start vacancy_{tenant['vacancy_id'].hex}")
    assert any("Бариста" in text for text in session.texts)


async def test_apply_without_questions_creates_application(bot, session, tenant):
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
        assert application is not None
        app_status = await db.get(ApplicationStatus, application.status_id)
    assert app_status.system_key == "new"
    assert application.answers == []


async def test_full_form_flow(bot, session, tenant):
    await _add_questions(
        tenant,
        {"text": "Как вас зовут?", "type": "short_text"},
        {"text": "Сколько вам лет?", "type": "number", "validation": {"min": 18, "max": 65}},
        {"text": "Смена?", "type": "single_choice", "options": ["Утро", "Вечер"]},
    )

    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    assert "Как вас зовут?" in session.last_text

    await _feed(bot, tenant, text="Аскар")
    assert "Сколько вам лет?" in session.last_text

    # Out of range -> re-ask rather than advance.
    session.clear()
    await _feed(bot, tenant, text="12")
    assert "не меньше 18" in session.last_text

    # Not a number at all -> same.
    session.clear()
    await _feed(bot, tenant, text="двадцать")
    assert "Введите число" in session.last_text

    session.clear()
    await _feed(bot, tenant, text="25")
    assert "Смена?" in session.last_text

    session.clear()
    await _feed(bot, tenant, data="opt:0")
    assert "Проверьте ваши ответы" in session.last_text

    await _feed(bot, tenant, data="submit")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application is not None
    answers = {a["question_text"]: a["answer"] for a in application.answers}
    assert answers == {"Как вас зовут?": "Аскар", "Сколько вам лет?": "25", "Смена?": "Утро"}


async def test_duplicate_application_is_blocked(bot, session, tenant):
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    session.clear()
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")

    assert "уже откликались" in session.last_text
    async with TestSession() as db:
        count = len((await db.scalars(select(Application))).all())
    assert count == 1


async def test_cancel_clears_the_form(bot, session, tenant):
    await _add_questions(tenant, {"text": "Как вас зовут?", "type": "short_text"})
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")

    await _feed(bot, tenant, text="/cancel")
    assert "отменено" in session.last_text

    # A later message is treated as a menu tap, not as an answer.
    session.clear()
    await _feed(bot, tenant, text="что-то")
    assert "Выберите раздел" in session.last_text

    async with TestSession() as db:
        assert await db.scalar(select(Application)) is None


async def test_optional_question_can_be_skipped(bot, session, tenant):
    await _add_questions(
        tenant, {"text": "Ссылка на резюме?", "type": "short_text", "is_required": False}
    )
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    await _feed(bot, tenant, data="skip")
    await _feed(bot, tenant, data="submit")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["skipped"] is True
    assert application.answers[0]["answer"] is None


async def test_required_question_cannot_be_skipped(bot, session, tenant):
    await _add_questions(tenant, {"text": "Как вас зовут?", "type": "short_text"})
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    session.clear()
    await _feed(bot, tenant, data="skip")

    async with TestSession() as db:
        assert await db.scalar(select(Application)) is None


async def test_multi_choice_requires_a_selection(bot, session, tenant):
    await _add_questions(
        tenant, {"text": "Навыки?", "type": "multi_choice", "options": ["Кофе", "Касса", "Зал"]}
    )
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")

    session.clear()
    await _feed(bot, tenant, data="mdone")
    # A bottom keyboard has no callback alert, so the warning arrives as a message.
    assert any("хотя бы один" in text for text in session.texts)

    await _feed(bot, tenant, data="mopt:0")
    await _feed(bot, tenant, data="mopt:2")
    await _feed(bot, tenant, data="mdone")
    await _feed(bot, tenant, data="submit")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == ["Кофе", "Зал"]


async def test_archived_vacancy_is_not_applicable(bot, session, tenant):
    async with TestSession() as db:
        vacancy = await db.get(Vacancy, tenant["vacancy_id"])
        vacancy.status = "archived"
        await db.commit()

    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    assert "больше не доступна" in session.last_text

    async with TestSession() as db:
        assert await db.scalar(select(Application)) is None


async def test_my_applications_shows_status(bot, session, tenant):
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    session.clear()
    await _feed(bot, tenant, text="📨 Мои заявки")
    assert "Бариста" in session.last_text
    assert "Новая" in session.last_text


# --------------------------------------------------------------------------- question markup


async def test_formatted_question_renders_as_telegram_html(bot, session, tenant):
    """An HR-authored Markdown question reaches the candidate as real formatting, not
    literal asterisks — the whole point of app/bot/markup.py."""
    await _add_questions(
        tenant,
        {
            "text": "**Ismingiz** va familiyangizni kiriting.\nPasportdagidek yozing.",
            "type": "short_text",
        },
    )
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")

    assert "<b>Ismingiz</b> va familiyangizni kiriting." in session.last_text
    assert "**" not in session.last_text
    assert "Pasportdagidek yozing." in session.last_text


async def test_formatted_question_reappears_correctly_in_the_summary(bot, session, tenant):
    await _add_questions(
        tenant, {"text": "Sizning _tajribangiz_ nechchi yil?", "type": "short_text"}
    )
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    await _feed(bot, tenant, text="3 yil")

    assert "<i>tajribangiz</i>" in session.last_text
    assert "_tajribangiz_" not in session.last_text


async def test_stored_answer_keeps_the_authors_raw_markdown(bot, session, tenant):
    """The panel and CSV export show ``question_text`` — it should read exactly as the HR
    wrote it, not as escaped HTML tags or converted markup."""
    await _add_questions(tenant, {"text": "**Ismingiz** kim?", "type": "short_text"})
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    await _feed(bot, tenant, text="Аскар")
    await _feed(bot, tenant, data="submit")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["question_text"] == "**Ismingiz** kim?"


async def test_unformatted_question_is_sent_as_plain_text(bot, session, tenant):
    """No forced emphasis: a question with no Markdown in it is sent exactly as written,
    not silently wrapped in <b> — the HR controls emphasis themselves via the toolbar."""
    await _add_questions(tenant, {"text": "Оддий савол?", "type": "short_text"})
    await _feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    assert "Оддий савол?" in session.last_text
    assert "<b>" not in session.last_text
