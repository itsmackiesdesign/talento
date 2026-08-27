"""Semantic candidate name/photo fields in immutable application snapshots."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.applications import _to_item
from app.bot.forms import build_answers_payload
from app.bot.fsm import QuestionSnapshot


def test_answer_payload_snapshots_candidate_profile_roles():
    questions = [
        QuestionSnapshot(
            id="name-id",
            text="Name?",
            type="short_text",
            profile_field="candidate_name",
        ),
        QuestionSnapshot(
            id="photo-id",
            text="Photo?",
            type="file",
            profile_field="candidate_photo",
        ),
    ]
    answers = {
        "name-id": {"value": "Aziza Karimova", "raw": "Aziza Karimova"},
        "photo-id": {
            "value": "portrait.jpg",
            "raw": "https://test.example.com/files/portrait.jpg",
        },
    }

    payload = build_answers_payload(questions, answers)

    assert payload[0]["profile_field"] == "candidate_name"
    assert payload[0]["answer"] == "Aziza Karimova"
    assert payload[0]["file_url"] is None
    assert payload[1]["profile_field"] == "candidate_photo"
    assert payload[1]["file_url"] == "https://test.example.com/files/portrait.jpg"


def test_application_item_uses_profile_answers_with_telegram_fallbacks():
    application = SimpleNamespace(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        answers=[
            {
                "profile_field": "candidate_name",
                "answer": "Aziza Karimova",
                "skipped": False,
            },
            {
                "profile_field": "candidate_photo",
                "answer": "portrait.jpg",
                "file_url": "https://test.example.com/files/portrait.jpg",
                "skipped": False,
            },
        ],
    )
    vacancy = SimpleNamespace(id=uuid.uuid4(), title="Designer")
    candidate = SimpleNamespace(
        first_name="Telegram name",
        telegram_username="aziza",
        phone="+998901234567",
    )
    application_status = SimpleNamespace(id=uuid.uuid4())

    item = _to_item(application, vacancy, candidate, None, application_status)

    assert item.candidate_name == "Aziza Karimova"
    assert item.candidate_photo_url == "https://test.example.com/files/portrait.jpg"

    application.answers = []
    fallback = _to_item(application, vacancy, candidate, None, application_status)
    assert fallback.candidate_name == "Telegram name"
    assert fallback.candidate_photo_url is None
