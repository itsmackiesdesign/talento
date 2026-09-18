from app.core.crypto import encrypt
from app.models import (
    Application,
    ApplicationStatus,
    Bot,
    Candidate,
    CompanyCandidate,
    VacancyCampaignRecipient,
)
from tests.conftest import BOT_TOKEN, TestSession, make_company


async def _vacancy(client, owner, title):
    response = await client.post(
        "/api/v1/vacancies",
        json={"title": title, "status": "active"},
        headers=owner["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _seed_audience(owner, target_id, source_id):
    async with TestSession() as db:
        new_status = await db.scalar(
            ApplicationStatus.__table__.select()
            .where(
                ApplicationStatus.company_id == owner["company_id"],
                ApplicationStatus.system_key == "new",
            )
            .with_only_columns(ApplicationStatus.id)
        )
        rejected_status = await db.scalar(
            ApplicationStatus.__table__.select()
            .where(
                ApplicationStatus.company_id == owner["company_id"],
                ApplicationStatus.system_key == "rejected",
            )
            .with_only_columns(ApplicationStatus.id)
        )
        db.add(
            Bot(
                company_id=owner["company_id"],
                token_encrypted=encrypt(BOT_TOKEN),
                bot_username="campaign_test_bot",
                webhook_secret="secret",
            )
        )
        candidates = [
            Candidate(telegram_user_id=1001, first_name="Source", language="ru"),
            Candidate(telegram_user_id=1002, first_name="Rejected", language="uz"),
            Candidate(telegram_user_id=1003, first_name="No application", language="en"),
            Candidate(telegram_user_id=1004, first_name="Opted out", language="ru"),
        ]
        db.add_all(candidates)
        await db.flush()
        db.add_all(
            [
                CompanyCandidate(
                    company_id=owner["company_id"],
                    candidate_id=candidate.id,
                    language=candidate.language,
                    notifications_enabled=index != 3,
                )
                for index, candidate in enumerate(candidates)
            ]
        )
        db.add_all(
            [
                Application(
                    company_id=owner["company_id"],
                    vacancy_id=source_id,
                    candidate_id=candidates[0].id,
                    status_id=new_status,
                ),
                Application(
                    company_id=owner["company_id"],
                    vacancy_id=target_id,
                    candidate_id=candidates[1].id,
                    status_id=rejected_status,
                ),
            ]
        )
        await db.commit()
        return str(new_status)


async def test_all_recipient_modes_and_exclusions(client):
    owner = await make_company(client)
    target = await _vacancy(client, owner, "Target")
    source = await _vacancy(client, owner, "Source")
    new_status_id = await _seed_audience(owner, target["id"], source["id"])
    endpoint = f"/api/v1/vacancies/{target['id']}/campaigns/estimate"

    everyone = await client.post(
        endpoint, json={"audience_type": "everyone"}, headers=owner["headers"]
    )
    assert everyone.status_code == 200
    assert everyone.json() == {"count": 3}

    candidate_response = await client.get(
        "/api/v1/vacancy-campaigns/candidates", headers=owner["headers"]
    )
    assert candidate_response.status_code == 200
    candidates = candidate_response.json()
    assert {candidate["first_name"] for candidate in candidates} == {
        "Source",
        "Rejected",
        "No application",
    }
    source_candidate_id = next(
        candidate["id"] for candidate in candidates if candidate["first_name"] == "Source"
    )
    explicitly_excluded = await client.post(
        endpoint,
        json={
            "audience_type": "everyone",
            "excluded_candidate_ids": [source_candidate_id],
        },
        headers=owner["headers"],
    )
    assert explicitly_excluded.json() == {"count": 2}

    not_applied = await client.post(
        endpoint,
        json={"audience_type": "everyone", "exclude_applied": True},
        headers=owner["headers"],
    )
    assert not_applied.json() == {"count": 2}

    without_rejected = await client.post(
        endpoint,
        json={"audience_type": "everyone", "exclude_rejected": True},
        headers=owner["headers"],
    )
    assert without_rejected.json() == {"count": 2}

    from_vacancy = await client.post(
        endpoint,
        json={
            "audience_type": "selected_vacancies",
            "source_vacancy_ids": [source["id"]],
        },
        headers=owner["headers"],
    )
    assert from_vacancy.json() == {"count": 1}

    from_status = await client.post(
        endpoint,
        json={"audience_type": "selected_statuses", "source_status_ids": [new_status_id]},
        headers=owner["headers"],
    )
    assert from_status.json() == {"count": 1}

    english = await client.post(
        endpoint,
        json={"audience_type": "everyone", "languages": ["en"]},
        headers=owner["headers"],
    )
    assert english.json() == {"count": 1}


async def test_campaign_creation_snapshots_deduplicated_recipients(client, monkeypatch):
    owner = await make_company(client)
    target = await _vacancy(client, owner, "Target")
    source = await _vacancy(client, owner, "Source")
    await _seed_audience(owner, target["id"], source["id"])
    enqueued = []

    monkeypatch.setattr(
        "app.api.vacancy_campaigns._enqueue_campaign",
        lambda campaign_id, scheduled_at: enqueued.append((campaign_id, scheduled_at)),
    )
    response = await client.post(
        f"/api/v1/vacancies/{target['id']}/campaigns",
        json={"audience_type": "everyone", "intro_text": "New role"},
        headers=owner["headers"],
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    assert campaign["total_recipients"] == 3
    assert campaign["status"] == "queued"
    assert len(enqueued) == 1

    async with TestSession() as db:
        recipients = list(
            await db.scalars(
                VacancyCampaignRecipient.__table__.select()
                .where(VacancyCampaignRecipient.campaign_id == campaign["id"])
                .with_only_columns(VacancyCampaignRecipient.id)
            )
        )
        assert len(recipients) == 3
