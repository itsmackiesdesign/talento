"""Semantic candidate name/photo fields in immutable application snapshots."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.applications import _to_item
from app.bot.forms import build_answers_payload
from app.bot.fsm import QuestionSnapshot
from app.core.config import settings
from app.services.storage import find_legacy_candidate_file_urls


def test_answer_payload_snapshots_candidate_profile_roles():
    questions = [
        QuestionSnapshot(
            id="name-id",
            text="Name?",
            type="short_text",
            profile_field="candidate_name",
            is_common=True,
        ),
        QuestionSnapshot(
            id="photo-id",
            text="Photo?",
            type="file",
            profile_field="candidate_photo",
        ),
        QuestionSnapshot(
            id="resume-id",
            text="Resume?",
            type="file",
        ),
    ]
    answers = {
        "name-id": {"value": "Aziza Karimova", "raw": "Aziza Karimova"},
        "photo-id": {
            "value": "portrait.jpg",
            "raw": "https://test.example.com/files/portrait.jpg",
        },
        "resume-id": {
            "value": "resume.pdf",
            "raw": "https://test.example.com/files/resume.pdf",
        },
    }

    payload = build_answers_payload(questions, answers)

    assert payload[0]["profile_field"] == "candidate_name"
    assert payload[0]["is_common"] is True
    assert payload[0]["answer"] == "Aziza Karimova"
    assert payload[0]["file_url"] is None
    assert payload[1]["profile_field"] == "candidate_photo"
    assert payload[1]["file_url"] == "https://test.example.com/files/portrait.jpg"
    # Keep every upload URL so turning the photo role on later also works for applications
    # submitted before that configuration change.
    assert payload[2]["profile_field"] is None
    assert payload[2]["file_url"] == "https://test.example.com/files/resume.pdf"


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


def test_application_item_resolves_legacy_answers_from_current_question_roles():
    name_question_id = uuid.uuid4()
    photo_question_id = uuid.uuid4()
    application = SimpleNamespace(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        answers=[
            {
                "question_id": str(name_question_id),
                "type": "short_text",
                "answer": "Legacy Candidate",
                "skipped": False,
            },
            {
                "question_id": photo_question_id.hex,
                "type": "file",
                "answer": "legacy portrait.jpg",
                "skipped": False,
            },
        ],
    )
    vacancy = SimpleNamespace(id=uuid.uuid4(), title="Designer")
    candidate = SimpleNamespace(
        first_name="Telegram name",
        telegram_username="legacy",
        phone=None,
    )
    application_status = SimpleNamespace(id=uuid.uuid4())

    item = _to_item(
        application,
        vacancy,
        candidate,
        None,
        application_status,
        {
            name_question_id.hex: "candidate_name",
            photo_question_id.hex: "candidate_photo",
        },
        {"candidate_name", "candidate_photo"},
        {"legacy portrait.jpg": "https://test.example.com/files/legacy-portrait.jpg"},
    )

    assert item.candidate_name == "Legacy Candidate"
    assert item.candidate_photo_url == "https://test.example.com/files/legacy-portrait.jpg"


def test_configured_name_role_does_not_use_telegram_for_unanswerable_old_application():
    application = SimpleNamespace(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        answers=[],
    )
    vacancy = SimpleNamespace(id=uuid.uuid4(), title="Designer")
    candidate = SimpleNamespace(
        first_name="Telegram name",
        telegram_username="legacy",
        phone=None,
    )
    application_status = SimpleNamespace(id=uuid.uuid4())

    item = _to_item(
        application,
        vacancy,
        candidate,
        None,
        application_status,
        {},
        {"candidate_name"},
    )

    assert item.candidate_name == "—"
    assert item.candidate_photo_url is None


def test_legacy_local_photo_is_recovered_only_when_filename_is_unique(tmp_path, monkeypatch):
    company_id = uuid.uuid4()
    upload_dir = tmp_path / "candidates" / str(company_id)
    upload_dir.mkdir(parents=True)
    (upload_dir / f"{uuid.uuid4().hex}-portrait photo.jpg").write_bytes(b"photo")
    (upload_dir / f"{uuid.uuid4().hex}-duplicate.jpg").write_bytes(b"one")
    (upload_dir / f"{uuid.uuid4().hex}-duplicate.jpg").write_bytes(b"two")
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BASE_URL", "https://test.example.com")
    monkeypatch.setattr(settings, "S3_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "S3_SECRET_KEY", "")
    monkeypatch.setattr(settings, "S3_BUCKET", "")

    resolved = find_legacy_candidate_file_urls(company_id, {"portrait photo.jpg", "duplicate.jpg"})

    assert resolved["portrait photo.jpg"].startswith(
        f"https://test.example.com/files/candidates/{company_id}/"
    )
    assert resolved["portrait photo.jpg"].endswith("-portrait%20photo.jpg")
    assert "duplicate.jpg" not in resolved
