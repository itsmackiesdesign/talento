"""Auth, company creation and — most importantly — tenant isolation."""

import pytest

from tests.conftest import make_company, register


async def test_register_returns_tokens(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "sup3rsecret", "full_name": "A"},
    )
    assert resp.status_code == 201
    assert {"access_token", "refresh_token"} <= resp.json().keys()


async def test_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "password": "sup3rsecret", "full_name": "A"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 409


async def test_login_and_refresh(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "b@example.com", "password": "sup3rsecret", "full_name": "B"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "b@example.com", "password": "sup3rsecret"}
    )
    assert login.status_code == 200

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


async def test_login_with_wrong_password_is_401(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "c@example.com", "password": "sup3rsecret", "full_name": "C"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "c@example.com", "password": "wrongpassword"}
    )
    assert resp.status_code == 401


async def test_access_token_is_not_accepted_as_refresh(client):
    """Token type is part of the payload; swapping one for the other must fail."""
    user = await register(client)
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": user["token"]})
    assert resp.status_code == 401


async def test_unauthenticated_requests_are_401(client):
    assert (await client.get("/api/v1/company")).status_code == 401


async def test_user_without_company_gets_403(client):
    user = await register(client)
    resp = await client.get("/api/v1/company", headers=user["headers"])
    assert resp.status_code == 403


async def test_company_creation_makes_caller_owner(client):
    owner = await make_company(client, "Acme Coffee")
    me = await client.get("/api/v1/auth/me", headers=owner["headers"])
    assert me.status_code == 200
    assert me.json()["role"] == "owner"
    assert me.json()["companies"][0]["name"] == "Acme Coffee"


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/vacancies"),
        ("get", "/api/v1/branches"),
        ("get", "/api/v1/questions"),
        ("get", "/api/v1/applications"),
        ("get", "/api/v1/company"),
        ("get", "/api/v1/dashboard/stats"),
    ],
)
async def test_foreign_company_header_is_rejected(client, method, path):
    """Passing another tenant's id in X-Company-Id must never grant access."""
    victim = await make_company(client, "Victim Ltd")
    attacker = await make_company(client, "Attacker Ltd")

    headers = {**attacker["headers"], "X-Company-Id": victim["company_id"]}
    resp = await getattr(client, method)(path, headers=headers)
    assert resp.status_code == 403, f"{path} leaked to another tenant: {resp.text}"


async def test_cannot_read_another_companys_vacancy_by_id(client):
    victim = await make_company(client, "Victim Ltd")
    attacker = await make_company(client, "Attacker Ltd")

    created = await client.post(
        "/api/v1/vacancies", json={"title": "Barista"}, headers=victim["headers"]
    )
    vacancy_id = created.json()["id"]

    # 404 rather than 403: a 403 would confirm the id exists.
    resp = await client.get(f"/api/v1/vacancies/{vacancy_id}", headers=attacker["headers"])
    assert resp.status_code == 404


async def test_second_company_per_user_is_rejected(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/companies", json={"name": "Another"}, headers=owner["headers"]
    )
    assert resp.status_code == 409
