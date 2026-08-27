"""The 'datetime' question type: API validation of the mask, and the candidate-facing
parsing for all three masks (date / datetime / time) end to end through the bot.
"""

from sqlalchemy import select

from app.bot.forms import ValidationError, validate_text_answer
from app.bot.fsm import QuestionSnapshot
from app.models import Application, Question
from tests.conftest import TestSession, make_company, tap
from tests.conftest import feed as _feed

# --------------------------------------------------------------------------- API


async def test_datetime_question_defaults_to_date_mask(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/questions",
        json={"text": "Качон туғилгансиз?", "type": "datetime"},
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["validation"] == {"mask": "date"}


async def test_datetime_question_accepts_each_mask(client):
    owner = await make_company(client)
    for mask in ("date", "datetime", "time"):
        resp = await client.post(
            "/api/v1/questions",
            json={"text": f"When ({mask})?", "type": "datetime", "validation": {"mask": mask}},
            headers=owner["headers"],
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["validation"] == {"mask": mask}


async def test_datetime_question_rejects_unknown_mask(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/questions",
        json={"text": "When?", "type": "datetime", "validation": {"mask": "quarterly"}},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_datetime_question_ignores_min_max(client):
    """min/max belong to number questions; sending them for datetime is silently dropped
    rather than accepted as meaningless state."""
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/questions",
        json={
            "text": "When?",
            "type": "datetime",
            "validation": {"mask": "time", "min": 5, "max": 10},
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["validation"] == {"mask": "time"}


async def test_patching_mask_revalidates_it(client):
    owner = await make_company(client)
    created = await client.post(
        "/api/v1/questions",
        json={"text": "When?", "type": "datetime"},
        headers=owner["headers"],
    )
    resp = await client.patch(
        f"/api/v1/questions/{created.json()['id']}",
        json={"validation": {"mask": "bogus"}},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_other_types_still_reject_stray_validation(client):
    """Sending a mask for a short_text question must not silently persist it."""
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/questions",
        json={"text": "Name?", "type": "short_text", "validation": {"mask": "date"}},
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["validation"] is None


# --------------------------------------------------------------------------- unit: parsing


def _q(mask: str) -> QuestionSnapshot:
    return QuestionSnapshot(id="1", text="When?", type="datetime", validation={"mask": mask})


def test_date_mask_accepts_zero_padded_input():
    assert validate_text_answer(_q("date"), "25.12.1999") == "25.12.1999"


def test_date_mask_rejects_missing_zero_padding():
    try:
        validate_text_answer(_q("date"), "5.2.1999")
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.key == "err_datetime_format"
        assert exc.kwargs["format"] == "DD.MM.YYYY"


def test_date_mask_rejects_impossible_calendar_date():
    """01.13.1999: no month 13. Caught by strptime, not just the regex."""
    for bad in ("32.01.1999", "30.02.1999", "29.02.1999"):  # 1999 is not a leap year
        try:
            validate_text_answer(_q("date"), bad)
            raise AssertionError(f"{bad!r} should have failed")
        except ValidationError:
            pass


def test_datetime_mask_requires_the_time_part():
    try:
        validate_text_answer(_q("datetime"), "25.12.1999")
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.kwargs["example"] == "25.12.1999 10:08"


def test_datetime_mask_accepts_full_value():
    assert validate_text_answer(_q("datetime"), "25.12.1999 10:08") == "25.12.1999 10:08"


def test_datetime_mask_rejects_invalid_hour():
    try:
        validate_text_answer(_q("datetime"), "25.12.1999 25:08")
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass


def test_time_mask_accepts_valid_time():
    assert validate_text_answer(_q("time"), "10:08") == "10:08"


def test_time_mask_rejects_hour_24():
    try:
        validate_text_answer(_q("time"), "24:00")
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass


def test_time_mask_rejects_date_shaped_input():
    """Answering a time question with a date must not be accidentally accepted."""
    try:
        validate_text_answer(_q("time"), "25.12.1999")
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass


def test_unknown_mask_falls_back_to_date():
    # Defensive: the API rejects an unknown mask before it can reach here, but a row edited
    # directly in the database should still degrade to something rather than crash the bot.
    assert validate_text_answer(_q("nonsense"), "25.12.1999") == "25.12.1999"


# --------------------------------------------------------------------------- end to end


async def _add_datetime_question(tenant, mask: str, required: bool = True):
    async with TestSession() as db:
        db.add(
            Question(
                company_id=tenant["company_id"],
                vacancy_id=tenant["vacancy_id"],
                text="Качон туғилгансиз?",
                type="datetime",
                validation={"mask": mask},
                is_required=required,
                sort_order=0,
            )
        )
        await db.commit()


async def test_bot_shows_the_format_hint(bot, session, tenant):
    await _add_datetime_question(tenant, "date")
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    assert "DD.MM.YYYY" in session.last_text
    assert "25.12.1999" in session.last_text


async def test_bot_rejects_bad_format_and_reasks(bot, session, tenant):
    await _add_datetime_question(tenant, "date")
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    session.clear()
    await tap(bot, tenant, "2/8/1999")
    assert "DD.MM.YYYY" in session.last_text

    async with TestSession() as db:
        assert await db.scalar(select(Application)) is None


async def test_bot_accepts_valid_date_and_stores_it(bot, session, tenant):
    await _add_datetime_question(tenant, "date")
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")
    await tap(bot, tenant, "25.12.1999")
    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == "25.12.1999"


async def test_bot_accepts_valid_datetime_and_stores_it(bot, session, tenant):
    await _add_datetime_question(tenant, "datetime")
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")
    await tap(bot, tenant, "25.12.1999 10:08")
    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == "25.12.1999 10:08"


async def test_bot_accepts_valid_time_and_stores_it(bot, session, tenant):
    await _add_datetime_question(tenant, "time")
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")
    await tap(bot, tenant, "10:08")
    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == "10:08"


async def test_optional_datetime_question_can_be_skipped(bot, session, tenant):
    await _add_datetime_question(tenant, "date", required=False)
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    assert "⏭ Пропустить" in session.buttons
    await tap(bot, tenant, "⏭ Пропустить")
    await tap(bot, tenant, "✅ Отправить")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["skipped"] is True


async def test_datetime_question_uses_the_plain_text_keyboard(bot, session, tenant):
    """Only Skip/Cancel — no special buttons, so any of the three masks is typed in."""
    await _add_datetime_question(tenant, "datetime", required=True)
    await _feed(bot, tenant, text="/start")
    await tap(bot, tenant, "📋 Вакансии")
    await tap(bot, tenant, "Бариста")
    await tap(bot, tenant, "✅ Откликнуться")

    assert session.buttons == ["✖️ Отменить"]
