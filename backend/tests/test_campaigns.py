"""Campaign links stay tenant-scoped and expose their real application count."""

from tests.conftest import make_company


async def _vacancy(client, owner, title: str) -> dict:
    response = await client.post(
        "/api/v1/vacancies",
        json={"title": title, "description": "Описание", "status": "active"},
        headers=owner["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_campaigns_are_scoped_to_their_vacancy_and_tenant(client):
    owner = await make_company(client, "Owner")
    other = await make_company(client, "Other")
    vacancy = await _vacancy(client, owner, "Бариста")
    foreign_vacancy = await _vacancy(client, other, "Кассир")

    created = await client.post(
        "/api/v1/campaigns",
        json={"vacancy_id": vacancy["id"], "name": "QR у входа", "source": "offline"},
        headers=owner["headers"],
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["vacancy_id"] == vacancy["id"]
    assert len(campaign["code"]) == 12
    assert campaign["applications_count"] == 0

    listing = await client.get(
        f"/api/v1/campaigns?vacancy_id={vacancy['id']}", headers=owner["headers"]
    )
    assert [item["id"] for item in listing.json()] == [campaign["id"]]

    paused = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        json={"is_active": False},
        headers=owner["headers"],
    )
    assert paused.status_code == 200
    assert paused.json()["is_active"] is False

    foreign_create = await client.post(
        "/api/v1/campaigns",
        json={"vacancy_id": foreign_vacancy["id"], "name": "Чужой QR"},
        headers=owner["headers"],
    )
    assert foreign_create.status_code == 404

    foreign_update = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        json={"is_active": True},
        headers=other["headers"],
    )
    assert foreign_update.status_code == 404
