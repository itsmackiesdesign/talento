"""Per-language content: API storage plus what the candidate actually sees in the bot."""

import uuid

from sqlalchemy import select

from app.core.crypto import encrypt
from app.core.i18n import clean_translations, localized, localized_options, normalise
from app.models import Application, Branch, Candidate, Company, Question, Vacancy
from app.models import Bot as BotModel
from tests.conftest import BOT_TOKEN, CANDIDATE_ID, TestSession, make_company
from tests.conftest import feed as _feed

# --------------------------------------------------------------------------- unit


def test_normalise_handles_ietf_tags():
    assert normalise("ru-RU") == "ru"
    assert normalise("EN") == "en"
    assert normalise("de") is None
    assert normalise(None) is None


def test_localized_falls_back_per_field():
    vacancy = Vacancy(
        title="Бариста",
        description="Описание",
        translations={"uz": {"title": "Barista"}},
    )
    # Translated field wins; untranslated one falls back rather than rendering blank.
    assert localized(vacancy, "title", "uz") == "Barista"
    assert localized(vacancy, "description", "uz") == "Описание"
    assert localized(vacancy, "title", "en") == "Бариста"
    assert localized(vacancy, "title", None) == "Бариста"


def test_blank_translation_is_treated_as_missing():
    vacancy = Vacancy(title="Бариста", translations={"uz": {"title": "   "}})
    assert localized(vacancy, "title", "uz") == "Бариста"


def test_option_translation_must_match_length():
    question = Question(
        options=["Утро", "Вечер"], translations={"uz": {"options": ["Ertalab"]}}
    )
    # A short list would misalign answers, so the whole translation is ignored.
    assert localized_options(question, "uz") == ["Утро", "Вечер"]

    question.translations = {"uz": {"options": ["Ertalab", "Kechqurun"]}}
    assert localized_options(question, "uz") == ["Ertalab", "Kechqurun"]


def test_clean_translations_drops_unknown_languages_and_fields():
    cleaned = clean_translations(
        {
            "uz": {"title": "Barista", "secret": "nope"},
            "de": {"title": "Barista"},
            "en": {"title": "   "},
        },
        allowed_fields=("title",),
        enabled_languages=["ru", "uz", "en"],
    )
    assert cleaned == {"uz": {"title": "Barista"}}


# --------------------------------------------------------------------------- API


async def test_company_starts_with_its_default_language(client):
    owner = await make_company(client)
    assert owner["company"]["enabled_languages"] == ["ru"]


async def test_enable_additional_languages(client):
    owner = await make_company(client)
    resp = await client.patch(
        "/api/v1/company",
        json={"enabled_languages": ["ru", "uz", "en"]},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["enabled_languages"] == ["ru", "uz", "en"]


async def test_duplicate_languages_are_collapsed(client):
    owner = await make_company(client)
    resp = await client.patch(
        "/api/v1/company",
        json={"enabled_languages": ["ru", "uz", "ru"]},
        headers=owner["headers"],
    )
    assert resp.json()["enabled_languages"] == ["ru", "uz"]


async def test_cannot_drop_the_default_language(client):
    """Everything falls back to the default, so it must stay published."""
    owner = await make_company(client)
    resp = await client.patch(
        "/api/v1/company", json={"enabled_languages": ["uz"]}, headers=owner["headers"]
    )
    assert resp.status_code == 422
    assert "default language" in resp.json()["detail"].lower()


async def test_switching_default_and_enabled_together_is_allowed(client):
    owner = await make_company(client)
    resp = await client.patch(
        "/api/v1/company",
        json={"default_language": "uz", "enabled_languages": ["uz", "ru"]},
        headers=owner["headers"],
    )
    assert resp.status_code == 200


async def test_unsupported_language_is_rejected(client):
    owner = await make_company(client)
    resp = await client.patch(
        "/api/v1/company", json={"enabled_languages": ["ru", "de"]}, headers=owner["headers"]
    )
    assert resp.status_code == 422


async def _multilingual_company(client):
    owner = await make_company(client)
    await client.patch(
        "/api/v1/company",
        json={"enabled_languages": ["ru", "uz", "en"]},
        headers=owner["headers"],
    )
    return owner


async def test_vacancy_translations_roundtrip(client):
    owner = await _multilingual_company(client)
    resp = await client.post(
        "/api/v1/vacancies",
        json={
            "title": "Бариста",
            "description": "Готовим кофе",
            "translations": {
                "uz": {"title": "Barista", "description": "Qahva tayyorlaymiz"},
                "en": {"title": "Barista"},
            },
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["translations"]["uz"]["title"] == "Barista"
    assert body["translations"]["en"] == {"title": "Barista"}


async def test_translations_for_disabled_language_are_dropped(client):
    owner = await make_company(client)  # only ru enabled
    resp = await client.post(
        "/api/v1/vacancies",
        json={"title": "Бариста", "translations": {"uz": {"title": "Barista"}}},
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["translations"] == {}


async def test_branch_translations_roundtrip(client):
    owner = await _multilingual_company(client)
    resp = await client.post(
        "/api/v1/branches",
        json={
            "name": "Филиал Чиланзар",
            "city": "Ташкент",
            "translations": {"uz": {"name": "Chilonzor filiali", "city": "Toshkent"}},
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["translations"]["uz"]["city"] == "Toshkent"


async def test_question_option_translation_length_must_match(client):
    owner = await _multilingual_company(client)
    resp = await client.post(
        "/api/v1/questions",
        json={
            "text": "Смена?",
            "type": "single_choice",
            "options": ["Утро", "Вечер"],
            "translations": {"uz": {"text": "Smena?", "options": ["Ertalab"]}},
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 422
    assert "options" in resp.json()["detail"]


async def test_question_translations_accepted_when_aligned(client):
    owner = await _multilingual_company(client)
    resp = await client.post(
        "/api/v1/questions",
        json={
            "text": "Смена?",
            "type": "single_choice",
            "options": ["Утро", "Вечер"],
            "translations": {"uz": {"text": "Smena?", "options": ["Ertalab", "Kechqurun"]}},
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["translations"]["uz"]["options"] == ["Ertalab", "Kechqurun"]


async def test_changing_base_options_revalidates_translations(client):
    """Shrinking the option list must not leave a stale translation of the old one."""
    owner = await _multilingual_company(client)
    created = await client.post(
        "/api/v1/questions",
        json={
            "text": "Смена?",
            "type": "single_choice",
            "options": ["Утро", "Вечер"],
            "translations": {"uz": {"options": ["Ertalab", "Kechqurun"]}},
        },
        headers=owner["headers"],
    )
    question_id = created.json()["id"]

    resp = await client.patch(
        f"/api/v1/questions/{question_id}",
        json={"options": ["Утро", "День", "Вечер"]},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_duplicate_carries_translations(client):
    owner = await _multilingual_company(client)
    vacancy = await client.post(
        "/api/v1/vacancies",
        json={"title": "Бариста", "translations": {"uz": {"title": "Barista"}}},
        headers=owner["headers"],
    )
    vacancy_id = vacancy.json()["id"]
    await client.post(
        "/api/v1/questions",
        json={
            "text": "Опыт?",
            "type": "short_text",
            "vacancy_id": vacancy_id,
            "translations": {"uz": {"text": "Tajriba?"}},
        },
        headers=owner["headers"],
    )

    copy = await client.post(
        f"/api/v1/vacancies/{vacancy_id}/duplicate", json={}, headers=owner["headers"]
    )
    assert copy.json()["translations"]["uz"]["title"] == "Barista"

    copied_questions = await client.get(
        f"/api/v1/questions?vacancy_id={copy.json()['id']}", headers=owner["headers"]
    )
    assert copied_questions.json()[0]["translations"]["uz"]["text"] == "Tajriba?"


async def test_bot_texts_can_be_translated(client):
    owner = await _multilingual_company(client)
    async with TestSession() as db:
        db.add(
            BotModel(
                company_id=uuid.UUID(owner["company_id"]),
                token_encrypted=encrypt(BOT_TOKEN),
                bot_username="acme_bot",
                webhook_secret="s3cret",
            )
        )
        await db.commit()

    resp = await client.patch(
        "/api/v1/bot",
        json={
            "welcome_message": "Привет!",
            "translations": {"uz": {"welcome_message": "Salom!"}},
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["translations"]["uz"]["welcome_message"] == "Salom!"


# --------------------------------------------------------------------------- bot


async def _pick_language(bot, tenant, code: str):
    await _feed(bot, tenant, data=f"setlang:{code}")


async def test_first_start_offers_a_language_picker(bot, session, multi_tenant):
    await _feed(bot, multi_tenant, text="/start")
    assert "Choose a language" in session.last_text
    assert session.buttons[:2] == ["✅ Русский", "O‘zbekcha"]


async def test_choosing_uzbek_switches_the_interface(bot, session, multi_tenant):
    await _pick_language(bot, multi_tenant, "uz")
    # Confirmation, with the main menu now rendered in Uzbek.
    assert any("O‘zbekcha" in text for text in session.texts)
    assert "📋 Vakansiyalar" in session.buttons

    session.clear()
    await _feed(bot, multi_tenant, text="/start")
    # Welcome now comes from the Uzbek bot-text translation, and the picker is not shown
    # again because the choice is remembered.
    assert "Xush kelibsiz!" in session.texts


async def test_vacancy_card_renders_in_the_chosen_language(bot, session, multi_tenant):
    await _pick_language(bot, multi_tenant, "uz")
    session.clear()

    await _feed(bot, multi_tenant, data=f"vac:{multi_tenant['vacancy_id'].hex}")
    assert "Barista" in session.last_text
    assert "Qahva tayyorlaymiz" in session.last_text
    # City has no Uzbek translation — it falls back rather than disappearing.
    assert "Ташкент" in session.last_text


async def test_vacancy_list_uses_translated_titles(bot, session, multi_tenant):
    await _pick_language(bot, multi_tenant, "uz")
    session.clear()

    await _feed(bot, multi_tenant, text="📋 Vakansiyalar")
    assert "Barista" in session.buttons


async def test_telegram_language_code_is_the_first_guess(bot, session, multi_tenant):
    """An Uzbek-locale client gets Uzbek without touching the picker."""
    await _feed(bot, multi_tenant, data=f"vac:{multi_tenant['vacancy_id'].hex}", language_code="uz")
    assert "Barista" in session.last_text


async def test_unpublished_language_falls_back_to_default(bot, session, multi_tenant):
    """The company does not publish in English, so an en client still sees Russian."""
    await _feed(bot, multi_tenant, data=f"vac:{multi_tenant['vacancy_id'].hex}", language_code="en")
    assert "Бариста" in session.last_text


async def test_answers_are_stored_in_the_base_language(bot, session, multi_tenant):
    """A candidate answering in Uzbek must still produce Russian data for HR."""
    async with TestSession() as db:
        db.add(
            Question(
                company_id=multi_tenant["company_id"],
                vacancy_id=multi_tenant["vacancy_id"],
                text="Смена?",
                type="single_choice",
                options=["Утро", "Вечер"],
                translations={"uz": {"text": "Smena?", "options": ["Ertalab", "Kechqurun"]}},
                sort_order=0,
            )
        )
        await db.commit()

    await _pick_language(bot, multi_tenant, "uz")
    session.clear()

    await _feed(bot, multi_tenant, data=f"apply:{multi_tenant['vacancy_id'].hex}")
    # The candidate is asked in Uzbek…
    assert "Smena?" in session.last_text
    assert session.buttons[:2] == ["Ertalab", "Kechqurun"]

    session.clear()
    await _feed(bot, multi_tenant, data="opt:1")
    # …and sees their own answer echoed back in Uzbek.
    assert "Kechqurun" in session.last_text

    await _feed(bot, multi_tenant, data="submit")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    answer = application.answers[0]
    # …but the panel gets the base wording for both the question and the answer.
    assert answer["question_text"] == "Смена?"
    assert answer["answer"] == "Вечер"


async def test_multi_choice_answers_are_stored_in_the_base_language(bot, session, multi_tenant):
    async with TestSession() as db:
        db.add(
            Question(
                company_id=multi_tenant["company_id"],
                vacancy_id=multi_tenant["vacancy_id"],
                text="Навыки?",
                type="multi_choice",
                options=["Кофе", "Касса", "Зал"],
                translations={
                    "uz": {"text": "Ko‘nikmalar?", "options": ["Qahva", "Kassa", "Zal"]}
                },
                sort_order=0,
            )
        )
        await db.commit()

    await _pick_language(bot, multi_tenant, "uz")
    await _feed(bot, multi_tenant, data=f"apply:{multi_tenant['vacancy_id'].hex}")
    await _feed(bot, multi_tenant, data="mopt:0")
    await _feed(bot, multi_tenant, data="mopt:2")
    await _feed(bot, multi_tenant, data="mdone")
    await _feed(bot, multi_tenant, data="submit")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
    assert application.answers[0]["answer"] == ["Кофе", "Зал"]


async def test_chosen_language_is_persisted_on_the_candidate(bot, session, multi_tenant):
    await _pick_language(bot, multi_tenant, "uz")
    await _feed(bot, multi_tenant, data=f"apply:{multi_tenant['vacancy_id'].hex}")

    async with TestSession() as db:
        candidate = await db.scalar(
            select(Candidate).where(Candidate.telegram_user_id == CANDIDATE_ID)
        )
    assert candidate.language == "uz"


async def test_single_language_company_never_shows_the_picker(bot, session, tenant):
    """The default fixture publishes in one language only."""
    await _feed(bot, tenant, text="/start")
    assert "Choose a language" not in session.last_text
    assert any("Здравствуйте" in text for text in session.texts)


async def test_branch_names_are_translated_in_the_branch_menu(bot, session, multi_tenant):
    async with TestSession() as db:
        branch = Branch(
            company_id=multi_tenant["company_id"],
            name="Филиал Чиланзар",
            city="Ташкент",
            translations={"uz": {"name": "Chilonzor filiali", "city": "Toshkent"}},
        )
        db.add(branch)
        await db.flush()

        vacancy = await db.get(Vacancy, multi_tenant["vacancy_id"])
        vacancy.branch_id = branch.id
        company = await db.get(Company, multi_tenant["company_id"])
        company.branches_enabled = True
        await db.commit()

    await _pick_language(bot, multi_tenant, "uz")
    session.clear()

    await _feed(bot, multi_tenant, text="📋 Vakansiyalar")
    assert any(
        "Chilonzor filiali" in label and "Toshkent" in label for label in session.buttons
    )
