"""The HR's own kanban pipeline: seeding, system-step locking, CRUD, reorder, deletion."""

from tests.conftest import make_company


async def _list(client, headers):
    resp = await client.get("/api/v1/application-statuses", headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def test_new_company_is_seeded_with_six_stages_in_order(client):
    owner = await make_company(client)
    rows = await _list(client, owner["headers"])

    assert [r["label"] for r in rows] == [
        "Новая", "Просмотрена", "Интервью", "Оффер", "Принят", "Отклонена",
    ]
    assert [r["is_system"] for r in rows] == [True, False, False, False, True, True]
    # System steps ship with ru/uz/en so candidate notifications always work, even though
    # the HR can never touch them.
    assert rows[0]["translations"]["en"]["label"] == "New"


async def test_custom_stage_lifecycle(client):
    owner = await make_company(client)

    created = await client.post(
        "/api/v1/application-statuses",
        json={"label": "Тестовое задание", "notify_candidate": True},
        headers=owner["headers"],
    )
    assert created.status_code == 201
    body = created.json()
    assert body["label"] == "Тестовое задание"
    assert body["is_system"] is False
    # New custom stages land just before the two terminal system steps.
    rows = await _list(client, owner["headers"])
    assert rows[-3]["id"] == body["id"]

    updated = await client.patch(
        f"/api/v1/application-statuses/{body['id']}",
        json={"label": "Тех. задание", "notify_candidate": False},
        headers=owner["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Тех. задание"
    assert updated.json()["notify_candidate"] is False

    deleted = await client.delete(
        f"/api/v1/application-statuses/{body['id']}", headers=owner["headers"]
    )
    assert deleted.status_code == 204
    assert body["id"] not in [r["id"] for r in await _list(client, owner["headers"])]


async def test_system_steps_reject_edit_and_delete(client):
    owner = await make_company(client)
    rows = await _list(client, owner["headers"])
    new_row = next(r for r in rows if r["label"] == "Новая")

    edited = await client.patch(
        f"/api/v1/application-statuses/{new_row['id']}",
        json={"label": "Hacked"},
        headers=owner["headers"],
    )
    assert edited.status_code == 400

    deleted = await client.delete(
        f"/api/v1/application-statuses/{new_row['id']}", headers=owner["headers"]
    )
    assert deleted.status_code == 400


async def test_deleting_a_stage_in_use_requires_reassignment(client):
    from tests.test_applications import _seed_application, _status_id

    owner = await make_company(client)
    interview_id = await _status_id(owner["company_id"], "interview")
    await _seed_application(owner["company_id"], status="interview")

    blocked = await client.delete(
        f"/api/v1/application-statuses/{interview_id}", headers=owner["headers"]
    )
    assert blocked.status_code == 400

    new_id = await _status_id(owner["company_id"], "new")
    moved = await client.delete(
        f"/api/v1/application-statuses/{interview_id}"
        f"?move_applications_to={new_id}",
        headers=owner["headers"],
    )
    assert moved.status_code == 204

    listing = await client.get("/api/v1/applications", headers=owner["headers"])
    assert listing.json()["items"][0]["status_id"] == new_id


async def test_reorder_accepts_only_the_full_custom_set(client):
    owner = await make_company(client)
    rows = await _list(client, owner["headers"])
    customs = [r["id"] for r in rows if not r["is_system"]]

    ok = await client.post(
        "/api/v1/application-statuses/reorder",
        json={"ids": list(reversed(customs))},
        headers=owner["headers"],
    )
    assert ok.status_code == 204
    reordered = await _list(client, owner["headers"])
    assert [r["id"] for r in reordered if not r["is_system"]] == list(reversed(customs))

    # Missing one of the customs (and no system ids allowed in) is rejected outright.
    partial = await client.post(
        "/api/v1/application-statuses/reorder",
        json={"ids": customs[:-1]},
        headers=owner["headers"],
    )
    assert partial.status_code == 400

    with_system = await client.post(
        "/api/v1/application-statuses/reorder",
        json={"ids": [rows[0]["id"], *customs]},
        headers=owner["headers"],
    )
    assert with_system.status_code == 400


async def test_statuses_are_tenant_isolated(client):
    owner = await make_company(client)
    other = await make_company(client, "Other")
    rows = await _list(client, other["headers"])
    # A custom (non-system) row so a 400 from _require_custom couldn't masquerade as the
    # tenant check actually firing — this must 404 on ownership, before that check runs.
    foreign_id = next(r for r in rows if not r["is_system"])["id"]

    resp = await client.patch(
        f"/api/v1/application-statuses/{foreign_id}",
        json={"label": "leak"},
        headers=owner["headers"],
    )
    assert resp.status_code == 404
