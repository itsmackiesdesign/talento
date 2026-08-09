"""The Sergosht-style navigation: 6-button menu, branch directory, 🔥/🌐 split, news.

Everything is driven by tapping, the way a candidate does it.
"""

import uuid

import pytest_asyncio
from sqlalchemy import select

from app.core.crypto import encrypt
from app.models import Bot as BotModel
from app.models import Branch, Company, News, Vacancy
from tests.conftest import BOT_TOKEN, TestSession, make_company, tap, tap_matching
from tests.conftest import _seed_default_statuses
from tests.conftest import feed as _feed


@pytest_asyncio.fixture
async def full_tenant():
    """Branch mode on, two branches, a hot vacancy, a branch vacancy and two news items."""
    async with TestSession() as db:
        company = Company(
            name="Acme",
            slug=f"acme-{uuid.uuid4().hex[:6]}",
            branches_enabled=True,
            enabled_languages=["ru"],
        )
        db.add(company)
        await db.flush()
        await _seed_default_statuses(db, company.id)

        bot_row = BotModel(
            company_id=company.id,
            token_encrypted=encrypt(BOT_TOKEN),
            bot_username="acme_hr_bot",
            webhook_secret="s3cret",
            about_text="Мы жарим мясо с 2018 года.",
            contacts_text="☎️ +998 90 123 45 67\nул. Бунёдкор, 12",
        )
        chilanzar = Branch(
            company_id=company.id,
            name="Чиланзар",
            city="Ташкент",
            address="ул. Бунёдкор, 12",
            latitude=41.2756,
            longitude=69.2035,
            sort_order=0,
        )
        yunusabad = Branch(
            company_id=company.id, name="Юнусабад", city="Ташкент", sort_order=1
        )
        db.add_all([bot_row, chilanzar, yunusabad])
        await db.flush()

        db.add_all(
            [
                Vacancy(
                    company_id=company.id, branch_id=chilanzar.id, title="Бариста",
                    description="Хорошая работа", status="active", sort_order=0,
                ),
                Vacancy(
                    company_id=company.id, title="Курьер", description="Свободный график",
                    status="active", is_hot=True, sort_order=1,
                ),
                News(
                    company_id=company.id, title="Открылся новый филиал",
                    content="Ждём вас в Юнусабаде", sort_order=0,
                ),
                News(
                    company_id=company.id, title="Повышаем зарплаты",
                    content="С октября", sort_order=1,
                ),
            ]
        )
        await db.commit()
        return {
            "company_id": company.id,
            "bot_id": bot_row.id,
            "branch_id": chilanzar.id,
        }


# --------------------------------------------------------------------------- menu shape


async def test_main_menu_has_all_six_sections(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    assert session.buttons == [
        "🏢 О компании",
        "📍 Филиалы",
        "📋 Вакансии",
        "📰 Новости",
        "☎️ Контакты / Адрес",
        "📨 Мои заявки",
    ]


async def test_menu_is_two_columns(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    markup = session.calls[-1].reply_markup
    assert [len(row) for row in markup.keyboard] == [2, 2, 2]


async def test_branches_button_hidden_without_branch_mode(bot, session, tenant):
    """The company answered 'no branches', so the section is omitted, not shown empty."""
    await _feed(bot, tenant, text="/start")
    assert "📍 Филиалы" not in session.buttons


async def test_menu_reflows_when_sections_are_hidden(bot, session, tenant):
    """Dropping Branches must not leave a hole in the grid."""
    await _feed(bot, tenant, text="/start")
    markup = session.calls[-1].reply_markup
    assert [len(row) for row in markup.keyboard] == [2, 2, 1]


async def test_language_button_appears_for_multilingual(bot, session, multi_tenant):
    await _feed(bot, multi_tenant, text="/start")
    await tap(bot, multi_tenant, "Русский")
    assert "🌐 Язык" in session.buttons


# --------------------------------------------------------------------------- sections


async def test_about_section(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "🏢 О компании")
    assert "жарим мясо" in session.last_text


async def test_contacts_section(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "☎️ Контакты / Адрес")
    assert "+998 90 123 45 67" in session.last_text


async def test_contacts_falls_back_when_unset(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    session.clear()
    await tap(bot, tenant, "☎️ Контакты / Адрес")
    assert "не заполнены" in session.last_text


# --------------------------------------------------------------------------- branches


async def test_branch_directory_lists_all_active_branches(bot, session, full_tenant):
    """The Branches section is a company directory — every branch, not just hiring ones."""
    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "📍 Филиалы")
    assert "Список филиалов" in session.last_text
    assert any("Чиланзар" in b for b in session.buttons)
    # Юнусабад has no vacancies but still belongs in the directory.
    assert any("Юнусабад" in b for b in session.buttons)


async def test_branch_directory_is_two_columns(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    await tap(bot, full_tenant, "📍 Филиалы")
    markup = session.calls[-1].reply_markup
    assert len(markup.keyboard[0]) == 2


async def test_branch_card_shows_address_and_sends_a_pin(bot, session, full_tenant):
    from aiogram.methods import SendLocation

    await _feed(bot, full_tenant, text="/start")
    await tap(bot, full_tenant, "📍 Филиалы")
    # Capture the label first: `buttons` reads the recorded calls, so clearing would
    # leave nothing to match against.
    label = next(b for b in session.buttons if "Чиланзар" in b)
    session.clear()
    await tap(bot, full_tenant, label)

    assert any("Бунёдкор" in text for text in session.texts)
    pins = [c for c in session.calls if isinstance(c, SendLocation)]
    assert len(pins) == 1
    assert round(pins[0].latitude, 4) == 41.2756


async def test_branch_without_coordinates_sends_no_pin(bot, session, full_tenant):
    from aiogram.methods import SendLocation

    await _feed(bot, full_tenant, text="/start")
    await tap(bot, full_tenant, "📍 Филиалы")
    label = next(b for b in session.buttons if "Юнусабад" in b)
    session.clear()
    await tap(bot, full_tenant, label)

    assert not [c for c in session.calls if isinstance(c, SendLocation)]


# --------------------------------------------------------------------------- 🔥 / 🌐


async def test_vacancy_type_menu_when_both_halves_exist(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "📋 Вакансии")
    assert session.buttons[:2] == ["🔥 Актуальные вакансии", "🌐 Вакансии по филиалам"]


async def test_hot_list_is_flat_and_branch_independent(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    await tap(bot, full_tenant, "📋 Вакансии")
    session.clear()
    await tap(bot, full_tenant, "🔥 Актуальные вакансии")

    assert "Курьер" in session.buttons
    # Бариста is not flagged hot, so it belongs only under the branch route.
    assert "Бариста" not in session.buttons


async def test_branch_route_reaches_the_branch_vacancy(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    await tap(bot, full_tenant, "📋 Вакансии")
    await tap(bot, full_tenant, "🌐 Вакансии по филиалам")
    await tap_matching(bot, full_tenant, session, "Чиланзар")
    assert "Бариста" in session.buttons


async def test_back_from_a_hot_vacancy_returns_to_the_hot_list(bot, session, full_tenant):
    """Not to a branch list — the candidate never chose a branch to get here."""
    await _feed(bot, full_tenant, text="/start")
    await tap(bot, full_tenant, "📋 Вакансии")
    await tap(bot, full_tenant, "🔥 Актуальные вакансии")
    await tap(bot, full_tenant, "Курьер")

    session.clear()
    await tap(bot, full_tenant, "⬅️ Назад")
    assert "Сейчас открыты" in session.last_text
    assert "Курьер" in session.buttons


async def test_type_menu_skipped_when_nothing_is_hot(bot, session, full_tenant):
    """A menu with one live option and one dead one is worse than no menu."""
    async with TestSession() as db:
        hot = await db.scalar(select(Vacancy).where(Vacancy.is_hot.is_(True)))
        hot.is_hot = False
        await db.commit()

    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "📋 Вакансии")
    assert "🔥 Актуальные вакансии" not in session.buttons
    assert "Выберите филиал" in session.last_text


async def test_no_branch_mode_goes_straight_to_a_flat_list(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    session.clear()
    await tap(bot, tenant, "📋 Вакансии")
    assert "Выберите вакансию" in session.last_text
    assert "Бариста" in session.buttons


async def test_applying_from_the_hot_list_still_works(bot, session, full_tenant):
    from app.models import Application

    await _feed(bot, full_tenant, text="/start")
    await tap(bot, full_tenant, "📋 Вакансии")
    await tap(bot, full_tenant, "🔥 Актуальные вакансии")
    await tap(bot, full_tenant, "Курьер")
    await tap(bot, full_tenant, "✅ Откликнуться")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application is not None


# --------------------------------------------------------------------------- news


async def test_news_section_sends_each_item(bot, session, full_tenant):
    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "📰 Новости")

    joined = "\n".join(session.texts)
    assert "Открылся новый филиал" in joined
    assert "Повышаем зарплаты" in joined


async def test_news_is_paginated_not_blasted(bot, session, full_tenant):
    """An unbounded feed sent one message per item is the fastest way to get rate-limited."""
    from app.bot.handlers import NEWS_PAGE_SIZE

    async with TestSession() as db:
        for i in range(NEWS_PAGE_SIZE + 4):
            db.add(
                News(
                    company_id=full_tenant["company_id"],
                    title=f"Новость {i}",
                    content="…",
                    sort_order=10 + i,
                )
            )
        await db.commit()

    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "📰 Новости")

    # One message per item on this page, plus the trailing menu message.
    assert len(session.texts) == NEWS_PAGE_SIZE + 1
    assert "➡️ Ещё новости" in session.buttons

    session.clear()
    await tap(bot, full_tenant, "➡️ Ещё новости")
    assert any("Новость" in text for text in session.texts)


async def test_unpublished_news_is_hidden(bot, session, full_tenant):
    async with TestSession() as db:
        for item in (await db.scalars(select(News))).all():
            item.is_published = False
        await db.commit()

    await _feed(bot, full_tenant, text="/start")
    session.clear()
    await tap(bot, full_tenant, "📰 Новости")
    assert "Новостей пока нет" in session.last_text


async def test_empty_news_returns_to_the_menu(bot, session, tenant):
    await _feed(bot, tenant, text="/start")
    session.clear()
    await tap(bot, tenant, "📰 Новости")
    assert "Новостей пока нет" in session.last_text
    assert "📋 Вакансии" in session.buttons


# --------------------------------------------------------------------------- news API


async def test_news_crud_and_tenant_isolation(client):
    owner = await make_company(client)
    other = await make_company(client, "Other")

    created = await client.post(
        "/api/v1/news",
        json={"title": "Открылись", "content": "Приходите"},
        headers=owner["headers"],
    )
    assert created.status_code == 201
    news_id = created.json()["id"]

    assert (await client.get("/api/v1/news", headers=owner["headers"])).json()[0][
        "title"
    ] == "Открылись"
    # Another tenant sees nothing and cannot touch it.
    assert (await client.get("/api/v1/news", headers=other["headers"])).json() == []
    patched = await client.patch(
        f"/api/v1/news/{news_id}", json={"title": "Hacked"}, headers=other["headers"]
    )
    assert patched.status_code == 404
    assert (
        await client.delete(f"/api/v1/news/{news_id}", headers=other["headers"])
    ).status_code == 404


async def test_news_translations_and_reorder(client):
    owner = await make_company(client)
    await client.patch(
        "/api/v1/company",
        json={"enabled_languages": ["ru", "uz"]},
        headers=owner["headers"],
    )

    first = await client.post(
        "/api/v1/news",
        json={"title": "Первая", "translations": {"uz": {"title": "Birinchi"}}},
        headers=owner["headers"],
    )
    second = await client.post(
        "/api/v1/news", json={"title": "Вторая"}, headers=owner["headers"]
    )
    assert first.json()["translations"]["uz"]["title"] == "Birinchi"

    resp = await client.post(
        "/api/v1/news/reorder",
        json={"ids": [second.json()["id"], first.json()["id"]]},
        headers=owner["headers"],
    )
    assert resp.status_code == 204
    listing = await client.get("/api/v1/news", headers=owner["headers"])
    assert [n["title"] for n in listing.json()] == ["Вторая", "Первая"]


# --------------------------------------------------------------------------- branch geo


async def test_branch_coordinates_must_come_in_pairs(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/branches",
        json={"name": "Чиланзар", "latitude": 41.2756},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_branch_coordinate_range_is_validated(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/branches",
        json={"name": "Чиланзар", "latitude": 200.0, "longitude": 69.2},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_patching_one_coordinate_is_rejected(client):
    """A half-updated pair would leave the row unable to render a pin."""
    owner = await make_company(client)
    created = await client.post(
        "/api/v1/branches",
        json={"name": "Чиланзар", "latitude": 41.2756, "longitude": 69.2035},
        headers=owner["headers"],
    )
    resp = await client.patch(
        f"/api/v1/branches/{created.json()['id']}",
        json={"latitude": 42.0},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_branch_geo_roundtrip(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/branches",
        json={
            "name": "Чиланзар",
            "photo_url": "https://example.com/b.jpg",
            "latitude": 41.2756,
            "longitude": 69.2035,
        },
        headers=owner["headers"],
    )
    body = resp.json()
    assert body["latitude"] == 41.2756
    assert body["photo_url"] == "https://example.com/b.jpg"


async def test_is_hot_roundtrip(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/vacancies",
        json={"title": "Курьер", "is_hot": True, "status": "active"},
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["is_hot"] is True
