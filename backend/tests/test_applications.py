"""Mini-ATS: statuses, history, comments, export, isolation."""

import json
import uuid
from unittest.mock import patch

from sqlalchemy import select

from app.models import (
    Application,
    ApplicationInterview,
    ApplicationStatus,
    ApplicationTask,
    Candidate,
    Vacancy,
)
from tests.conftest import TestSession, make_company

# The three system stages plus the three custom ones every company is seeded with (see
# DEFAULT_APPLICATION_STAGES in app/models.py) — tests look a status up by this key rather
# than assuming an id, the same way the panel does after fetching /application-statuses.
_CUSTOM_LABELS = {"viewed": "Просмотрена", "interview": "Интервью", "offer": "Оффер"}


async def _status_id(company_id: str, key: str) -> str:
    async with TestSession() as db:
        if key in ("new", "hired", "rejected"):
            row = await db.scalar(
                select(ApplicationStatus).where(
                    ApplicationStatus.company_id == uuid.UUID(company_id),
                    ApplicationStatus.system_key == key,
                )
            )
        else:
            row = await db.scalar(
                select(ApplicationStatus).where(
                    ApplicationStatus.company_id == uuid.UUID(company_id),
                    ApplicationStatus.label == _CUSTOM_LABELS[key],
                )
            )
    assert row is not None, f"status {key!r} not seeded for company {company_id}"
    return str(row.id)


async def _seed_application(
    company_id: str,
    title="Бариста",
    status="new",
    answers=None,
    candidate_name="Аскар",
    telegram_user_id: int | None = None,
    candidate_username="askar",
    candidate_phone="+998901234567",
):
    status_id = await _status_id(company_id, status)
    async with TestSession() as db:
        vacancy = Vacancy(company_id=uuid.UUID(company_id), title=title, status="active")
        candidate = Candidate(
            company_id=uuid.UUID(company_id),
            telegram_user_id=telegram_user_id or uuid.uuid4().int % 10**9,
            telegram_username=candidate_username,
            first_name=candidate_name,
            phone=candidate_phone,
        )
        db.add_all([vacancy, candidate])
        await db.flush()
        application = Application(
            company_id=uuid.UUID(company_id),
            vacancy_id=vacancy.id,
            candidate_id=candidate.id,
            status_id=uuid.UUID(status_id),
            answers=answers
            or [
                {
                    "question_id": "q1",
                    "question_text": "Ваш опыт?",
                    "type": "short_text",
                    "answer": "2 года",
                    "skipped": False,
                }
            ],
            candidate_name=candidate_name,
            candidate_telegram_user_id=candidate.telegram_user_id,
            candidate_username=candidate_username,
            candidate_phone=candidate_phone,
            candidate_language="ru",
        )
        db.add(application)
        await db.commit()
        return {
            "application_id": str(application.id),
            "vacancy_id": str(vacancy.id),
            "candidate_id": str(candidate.id),
        }


# Celery is not running in tests; the enqueue call is a no-op we assert on separately.
def _no_celery():
    return patch("app.workers.tasks.notify_candidate_status.delay")


async def test_list_and_filter(client):
    owner = await make_company(client)
    await _seed_application(owner["company_id"], "Бариста")
    await _seed_application(owner["company_id"], "Кассир", status="interview")

    listing = await client.get("/api/v1/applications", headers=owner["headers"])
    assert listing.status_code == 200
    assert listing.json()["total"] == 2

    interview_id = await _status_id(owner["company_id"], "interview")
    filtered = await client.get(
        f"/api/v1/applications?status={interview_id}", headers=owner["headers"]
    )
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["vacancy_title"] == "Кассир"


async def test_candidate_identity_is_tenant_scoped_and_application_contact_is_immutable(client):
    first = await make_company(client, "First")
    second = await make_company(client, "Second")
    shared_telegram_id = 777_000_111

    first_app = await _seed_application(
        first["company_id"],
        candidate_name="Алия Первая",
        telegram_user_id=shared_telegram_id,
        candidate_username="first_alias",
        candidate_phone="+998900000001",
    )
    await _seed_application(
        second["company_id"],
        candidate_name="Алия Вторая",
        telegram_user_id=shared_telegram_id,
        candidate_username="second_alias",
        candidate_phone="+998900000002",
    )

    async with TestSession() as db:
        candidates = (
            await db.scalars(
                select(Candidate)
                .where(Candidate.telegram_user_id == shared_telegram_id)
                .order_by(Candidate.company_id)
            )
        ).all()
        assert len(candidates) == 2
        first_candidate = await db.get(Candidate, uuid.UUID(first_app["candidate_id"]))
        first_candidate.first_name = "Позднее имя"
        first_candidate.telegram_username = "later_alias"
        first_candidate.phone = "+998909999999"
        await db.commit()

    first_listing = await client.get("/api/v1/applications", headers=first["headers"])
    second_listing = await client.get("/api/v1/applications", headers=second["headers"])

    assert first_listing.status_code == 200, first_listing.text
    assert second_listing.status_code == 200, second_listing.text
    assert first_listing.json()["total"] == 1
    assert first_listing.json()["items"][0]["candidate_name"] == "Алия Первая"
    assert first_listing.json()["items"][0]["candidate_username"] == "first_alias"
    assert first_listing.json()["items"][0]["candidate_phone"] == "+998900000001"
    assert second_listing.json()["total"] == 1
    assert second_listing.json()["items"][0]["candidate_name"] == "Алия Вторая"
    assert second_listing.json()["items"][0]["candidate_username"] == "second_alias"
    assert second_listing.json()["items"][0]["candidate_phone"] == "+998900000002"

    original_search = await client.get(
        "/api/v1/applications", params={"search": "Первая"}, headers=first["headers"]
    )
    mutable_search = await client.get(
        "/api/v1/applications", params={"search": "Позднее"}, headers=first["headers"]
    )
    assert original_search.json()["total"] == 1
    assert mutable_search.json()["total"] == 0


async def test_candidate_profile_name_and_photo_are_displayed_and_searchable(client):
    owner = await make_company(client)
    photo_url = "https://test.example.com/files/candidates/portrait.jpg"
    await _seed_application(
        owner["company_id"],
        answers=[
            {
                "question_id": uuid.uuid4().hex,
                "question_text": "Ваше имя?",
                "type": "short_text",
                "answer": "Азиза Каримова",
                "skipped": False,
                "profile_field": "candidate_name",
                "file_url": None,
            },
            {
                "question_id": uuid.uuid4().hex,
                "question_text": "Ваше фото",
                "type": "file",
                "answer": "portrait.jpg",
                "skipped": False,
                "profile_field": "candidate_photo",
                "file_url": photo_url,
            },
        ],
    )

    response = await client.get(
        "/api/v1/applications", params={"search": "Карим"}, headers=owner["headers"]
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["candidate_name"] == "Азиза Каримова"
    assert item["candidate_photo_url"] == photo_url


async def test_legacy_candidate_name_uses_current_question_role_and_is_searchable(client):
    owner = await make_company(client)
    question = await client.post(
        "/api/v1/questions",
        json={
            "text": "Ваше имя?",
            "type": "short_text",
            "profile_field": "candidate_name",
        },
        headers=owner["headers"],
    )
    assert question.status_code == 201, question.text
    question_id = uuid.UUID(question.json()["id"])

    await _seed_application(
        owner["company_id"],
        answers=[
            {
                "question_id": question_id.hex,
                "question_text": "Ваше имя?",
                "type": "short_text",
                "answer": "Старый кандидат",
                "skipped": False,
            }
        ],
    )

    response = await client.get(
        "/api/v1/applications",
        params={"search": "Старый"},
        headers=owner["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["candidate_name"] == "Старый кандидат"


async def test_filter_by_single_choice_answer(client):
    owner = await make_company(client)
    qid = uuid.uuid4()
    await _seed_application(
        owner["company_id"],
        "Бариста",
        answers=[
            {
                "question_id": qid.hex,
                "question_text": "Вы студент?",
                "type": "single_choice",
                "answer": "Да",
                "skipped": False,
            }
        ],
    )
    await _seed_application(
        owner["company_id"],
        "Кассир",
        answers=[
            {
                "question_id": qid.hex,
                "question_text": "Вы студент?",
                "type": "single_choice",
                "answer": "Нет",
                "skipped": False,
            }
        ],
    )

    resp = await client.get(
        "/api/v1/applications",
        params={"answers": json.dumps({str(qid): "Да"})},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["vacancy_title"] == "Бариста"


async def test_filter_by_multi_choice_answer(client):
    owner = await make_company(client)
    qid = uuid.uuid4()
    await _seed_application(
        owner["company_id"],
        "Бариста",
        answers=[
            {
                "question_id": qid.hex,
                "question_text": "Навыки",
                "type": "multi_choice",
                "answer": ["Python", "SQL"],
                "skipped": False,
            }
        ],
    )
    await _seed_application(
        owner["company_id"],
        "Кассир",
        answers=[
            {
                "question_id": qid.hex,
                "question_text": "Навыки",
                "type": "multi_choice",
                "answer": ["JavaScript"],
                "skipped": False,
            }
        ],
    )

    resp = await client.get(
        "/api/v1/applications",
        params={"answers": json.dumps({str(qid): "SQL"})},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["vacancy_title"] == "Бариста"


async def test_combining_two_answer_filters_requires_both(client):
    owner = await make_company(client)
    student_q, remote_q = uuid.uuid4(), uuid.uuid4()

    def answers(student: str, remote: str):
        return [
            {
                "question_id": student_q.hex,
                "question_text": "Студент?",
                "type": "single_choice",
                "answer": student,
                "skipped": False,
            },
            {
                "question_id": remote_q.hex,
                "question_text": "Удалённо?",
                "type": "single_choice",
                "answer": remote,
                "skipped": False,
            },
        ]

    await _seed_application(owner["company_id"], "Оба да", answers=answers("Да", "Да"))
    await _seed_application(owner["company_id"], "Только студент", answers=answers("Да", "Нет"))

    resp = await client.get(
        "/api/v1/applications",
        params={"answers": json.dumps({str(student_q): "Да", str(remote_q): "Да"})},
        headers=owner["headers"],
    )
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["vacancy_title"] == "Оба да"


async def test_answers_filter_rejects_malformed_input(client):
    owner = await make_company(client)

    not_json = await client.get(
        "/api/v1/applications", params={"answers": "not json"}, headers=owner["headers"]
    )
    assert not_json.status_code == 400

    not_object = await client.get(
        "/api/v1/applications", params={"answers": json.dumps(["a", "b"])}, headers=owner["headers"]
    )
    assert not_object.status_code == 400

    bad_question_id = await client.get(
        "/api/v1/applications",
        params={"answers": json.dumps({"not-a-uuid": "Да"})},
        headers=owner["headers"],
    )
    assert bad_question_id.status_code == 400


async def test_status_change_writes_history(client):
    owner = await make_company(client)
    seed = await _seed_application(owner["company_id"])
    interview_id = await _status_id(owner["company_id"], "interview")

    with _no_celery():
        resp = await client.patch(
            f"/api/v1/applications/{seed['application_id']}/status",
            json={"status_id": interview_id, "reason": "Подтвердил удобное время интервью"},
            headers=owner["headers"],
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status_id"] == interview_id

    transitions = [(h["from_status_label"], h["to_status_label"]) for h in body["history"]]
    assert ("Новая", "Интервью") in transitions
    assert body["history"][-1]["reason"] == "Подтвердил удобное время интервью"
    assert body["history"][-1]["changed_by_name"] == "Test User"


async def test_repeated_same_status_does_not_duplicate_history(client):
    owner = await make_company(client)
    seed = await _seed_application(owner["company_id"])
    viewed_id = await _status_id(owner["company_id"], "viewed")

    with _no_celery():
        for _ in range(3):
            await client.patch(
                f"/api/v1/applications/{seed['application_id']}/status",
                json={"status_id": viewed_id},
                headers=owner["headers"],
            )

    detail = await client.get(
        f"/api/v1/applications/{seed['application_id']}", headers=owner["headers"]
    )
    assert len(detail.json()["history"]) == 1


async def test_bulk_status_change_is_atomic_and_writes_history(client):
    owner = await make_company(client)
    first = await _seed_application(owner["company_id"], "Бариста")
    second = await _seed_application(owner["company_id"], "Кассир")
    interview_id = await _status_id(owner["company_id"], "interview")

    with _no_celery() as notify:
        response = await client.patch(
            "/api/v1/applications/bulk/status",
            json={
                "application_ids": [first["application_id"], second["application_id"]],
                "status_id": interview_id,
            },
            headers=owner["headers"],
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"requested": 2, "updated": 2, "unchanged": 0}
    assert notify.call_count == 2

    for application_id in (first["application_id"], second["application_id"]):
        detail = await client.get(
            f"/api/v1/applications/{application_id}", headers=owner["headers"]
        )
        assert detail.json()["status_id"] == interview_id
        assert detail.json()["history"][-1]["to_status_label"] == "Интервью"


async def test_bulk_status_change_rejects_foreign_ids_without_partial_update(client):
    owner = await make_company(client, "Owner")
    other = await make_company(client, "Other")
    own = await _seed_application(owner["company_id"])
    foreign = await _seed_application(other["company_id"])
    interview_id = await _status_id(owner["company_id"], "interview")
    new_id = await _status_id(owner["company_id"], "new")

    with _no_celery() as notify:
        response = await client.patch(
            "/api/v1/applications/bulk/status",
            json={
                "application_ids": [own["application_id"], foreign["application_id"]],
                "status_id": interview_id,
            },
            headers=owner["headers"],
        )

    assert response.status_code == 404
    assert notify.call_count == 0
    detail = await client.get(
        f"/api/v1/applications/{own['application_id']}", headers=owner["headers"]
    )
    assert detail.json()["status_id"] == new_id


async def test_invalid_status_is_rejected(client):
    owner = await make_company(client)
    seed = await _seed_application(owner["company_id"])
    resp = await client.patch(
        f"/api/v1/applications/{seed['application_id']}/status",
        json={"status_id": "promoted"},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_status_transition_reason_is_bounded(client):
    owner = await make_company(client)
    seed = await _seed_application(owner["company_id"])
    interview_id = await _status_id(owner["company_id"], "interview")

    response = await client.patch(
        f"/api/v1/applications/{seed['application_id']}/status",
        json={"status_id": interview_id, "reason": "x" * 1001},
        headers=owner["headers"],
    )

    assert response.status_code == 422


async def test_candidate_workspace_interviews_are_scoped_and_updatable(client):
    owner = await make_company(client, "Owner")
    other = await make_company(client, "Other")
    own = await _seed_application(owner["company_id"])
    foreign = await _seed_application(other["company_id"])

    created = await client.post(
        f"/api/v1/applications/{own['application_id']}/interviews",
        json={
            "kind": "video",
            "scheduled_at": "2026-09-12T10:30:00Z",
            "duration_minutes": 45,
            "location": "https://meet.example.com/talento",
            "notes": "Проверить опыт с кассой",
        },
        headers=owner["headers"],
    )
    assert created.status_code == 201, created.text
    interview = created.json()
    assert interview["status"] == "scheduled"
    assert interview["duration_minutes"] == 45

    detail = await client.get(
        f"/api/v1/applications/{own['application_id']}", headers=owner["headers"]
    )
    assert detail.json()["interviews"][0]["notes"] == "Проверить опыт с кассой"

    completed = await client.patch(
        f"/api/v1/applications/{own['application_id']}/interviews/{interview['id']}",
        json={"status": "completed", "location": None},
        headers=owner["headers"],
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["location"] is None

    cross_tenant = await client.patch(
        f"/api/v1/applications/{foreign['application_id']}/interviews/{interview['id']}",
        json={"status": "cancelled"},
        headers=other["headers"],
    )
    assert cross_tenant.status_code == 404

    async with TestSession() as db:
        stored = await db.get(ApplicationInterview, uuid.UUID(interview["id"]))
        assert stored is not None
        assert stored.status == "completed"


async def test_completed_interview_accepts_one_tenant_scoped_scorecard(client):
    owner = await make_company(client, "Owner")
    other = await make_company(client, "Other")
    own = await _seed_application(owner["company_id"])
    foreign = await _seed_application(other["company_id"])

    created = await client.post(
        f"/api/v1/applications/{own['application_id']}/interviews",
        json={
            "kind": "in_person",
            "scheduled_at": "2026-09-12T10:30:00Z",
            "duration_minutes": 45,
        },
        headers=owner["headers"],
    )
    assert created.status_code == 201, created.text
    interview_id = created.json()["id"]
    scorecard_path = (
        f"/api/v1/applications/{own['application_id']}/interviews/{interview_id}/scorecard"
    )

    premature = await client.post(
        scorecard_path,
        json={"rating": 5, "recommendation": "strong_yes", "summary": "Отличный опыт"},
        headers=owner["headers"],
    )
    assert premature.status_code == 409

    completed = await client.patch(
        f"/api/v1/applications/{own['application_id']}/interviews/{interview_id}",
        json={"status": "completed"},
        headers=owner["headers"],
    )
    assert completed.status_code == 200, completed.text

    saved = await client.post(
        scorecard_path,
        json={
            "rating": 5,
            "recommendation": "strong_yes",
            "summary": "Сильная коммуникация и релевантный опыт",
        },
        headers=owner["headers"],
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["recommendation"] == "strong_yes"

    detail = await client.get(
        f"/api/v1/applications/{own['application_id']}", headers=owner["headers"]
    )
    assert detail.json()["interviews"][0]["scorecard"]["rating"] == 5

    duplicate = await client.post(
        scorecard_path,
        json={"rating": 4, "recommendation": "yes", "summary": "Повтор"},
        headers=owner["headers"],
    )
    assert duplicate.status_code == 409

    cross_tenant = await client.post(
        f"/api/v1/applications/{foreign['application_id']}/interviews/{interview_id}/scorecard",
        json={"rating": 4, "recommendation": "yes", "summary": "Чужая заявка"},
        headers=other["headers"],
    )
    assert cross_tenant.status_code == 404


async def test_status_from_another_company_is_rejected(client):
    owner = await make_company(client)
    other = await make_company(client, "Other")
    seed = await _seed_application(owner["company_id"])
    foreign_id = await _status_id(other["company_id"], "interview")

    resp = await client.patch(
        f"/api/v1/applications/{seed['application_id']}/status",
        json={"status_id": foreign_id},
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_comments_roundtrip(client):
    owner = await make_company(client)
    seed = await _seed_application(owner["company_id"])

    created = await client.post(
        f"/api/v1/applications/{seed['application_id']}/comments",
        json={"text": "Позвонить завтра"},
        headers=owner["headers"],
    )
    assert created.status_code == 201
    assert created.json()["author_name"] == "Test User"

    detail = await client.get(
        f"/api/v1/applications/{seed['application_id']}", headers=owner["headers"]
    )
    assert [c["text"] for c in detail.json()["comments"]] == ["Позвонить завтра"]


async def test_csv_export_contains_all_columns(client):
    owner = await make_company(client)
    await _seed_application(owner["company_id"])

    resp = await client.get("/api/v1/applications/export?format=csv", headers=owner["headers"])
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]

    body = resp.text
    header, row = body.strip().splitlines()[:2]
    for column in ("Дата", "Филиал", "Вакансия", "Имя", "Телефон", "Username", "Статус"):
        assert column in header
    # The dynamic question column and its answer must both be present.
    assert "Ваш опыт?" in header
    assert "2 года" in row
    assert "+998901234567" in row
    assert "@askar" in row
    assert "Новая" in row


async def test_csv_export_respects_search_filter(client):
    owner = await make_company(client)
    await _seed_application(owner["company_id"], "Бариста", candidate_name="Аскар")
    await _seed_application(owner["company_id"], "Кассир", candidate_name="Малика")

    response = await client.get(
        "/api/v1/applications/export",
        params={"format": "csv", "search": "Малика"},
        headers=owner["headers"],
    )

    assert response.status_code == 200
    assert "Малика" in response.text
    assert "Аскар" not in response.text


async def test_export_rejects_unsupported_format(client):
    owner = await make_company(client)
    resp = await client.get("/api/v1/applications/export?format=pdf", headers=owner["headers"])
    assert resp.status_code == 400


async def test_applications_are_tenant_isolated(client):
    victim = await make_company(client, "Victim")
    attacker = await make_company(client, "Attacker")
    seed = await _seed_application(victim["company_id"])

    listing = await client.get("/api/v1/applications", headers=attacker["headers"])
    assert listing.json()["total"] == 0

    detail = await client.get(
        f"/api/v1/applications/{seed['application_id']}", headers=attacker["headers"]
    )
    assert detail.status_code == 404

    victim_hired_id = await _status_id(victim["company_id"], "hired")
    with _no_celery():
        patched = await client.patch(
            f"/api/v1/applications/{seed['application_id']}/status",
            json={"status_id": victim_hired_id},
            headers=attacker["headers"],
        )
    assert patched.status_code == 404

    commented = await client.post(
        f"/api/v1/applications/{seed['application_id']}/comments",
        json={"text": "leak"},
        headers=attacker["headers"],
    )
    assert commented.status_code == 404


async def test_dashboard_counts_only_own_company(client):
    victim = await make_company(client, "Victim")
    attacker = await make_company(client, "Attacker")
    await _seed_application(victim["company_id"])

    stats = await client.get("/api/v1/dashboard/stats", headers=attacker["headers"])
    assert stats.json()["applications_total"] == 0

    own = await client.get("/api/v1/dashboard/stats", headers=victim["headers"])
    body = own.json()
    new_id = await _status_id(victim["company_id"], "new")
    assert body["applications_total"] == 1
    assert body["by_status"][new_id] == 1
    assert body["active_vacancies"] == 1
    assert len(body["daily"]) == 31  # 30-day window, inclusive of both ends


async def test_delete_application_for_gdpr_request(client):
    owner = await make_company(client)
    seed = await _seed_application(owner["company_id"])

    resp = await client.delete(
        f"/api/v1/applications/{seed['application_id']}", headers=owner["headers"]
    )
    assert resp.status_code == 204

    listing = await client.get("/api/v1/applications", headers=owner["headers"])
    assert listing.json()["total"] == 0


async def test_candidate_workspace_next_actions_are_scoped_and_completable(client):
    owner = await make_company(client)
    other = await make_company(client, "Other")
    seed = await _seed_application(owner["company_id"])
    task = await client.post(
        f"/api/v1/applications/{seed['application_id']}/tasks",
        json={"title": "Позвонить кандидату", "due_at": "2026-09-11T09:00:00Z"},
        headers=owner["headers"],
    )

    assert task.status_code == 201, task.text
    task_id = task.json()["id"]
    detail = await client.get(
        f"/api/v1/applications/{seed['application_id']}", headers=owner["headers"]
    )
    assert detail.status_code == 200
    assert detail.json()["tasks"] == [
        {
            "id": task_id,
            "title": "Позвонить кандидату",
            "due_at": "2026-09-11T09:00:00Z",
            "completed_at": None,
            "created_at": task.json()["created_at"],
        }
    ]

    completed = await client.patch(
        f"/api/v1/applications/{seed['application_id']}/tasks/{task_id}",
        json={"completed": True},
        headers=owner["headers"],
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["completed_at"] is not None

    forbidden = await client.patch(
        f"/api/v1/applications/{seed['application_id']}/tasks/{task_id}",
        json={"completed": False},
        headers=other["headers"],
    )
    assert forbidden.status_code == 404

    async with TestSession() as db:
        stored = await db.scalar(select(ApplicationTask))
    assert stored is not None
    assert stored.completed_at is not None
