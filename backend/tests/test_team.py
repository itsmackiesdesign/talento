"""Tenant team invitations, membership management, and owner permissions."""

from sqlalchemy import select

from app.models import TeamInvitation
from tests.conftest import TestSession, make_company, register


def _token(invitation: dict) -> str:
    return invitation["invite_url"].rsplit("/", 1)[-1]


async def _invite_and_accept(client, owner, email="member@example.com"):
    invitation = await client.post(
        "/api/v1/company/team/invitations",
        json={"email": email},
        headers=owner["headers"],
    )
    assert invitation.status_code == 201, invitation.text
    member = await register(client, email)
    accepted = await client.post(
        f"/api/v1/team/invitations/{_token(invitation.json())}/accept",
        headers=member["headers"],
    )
    assert accepted.status_code == 200, accepted.text
    return member, invitation.json()


async def test_owner_can_invite_and_user_can_accept(client):
    owner = await make_company(client, "Acme Coffee")
    invitation = await client.post(
        "/api/v1/company/team/invitations",
        json={"email": "RECRUITER@example.com"},
        headers=owner["headers"],
    )
    assert invitation.status_code == 201, invitation.text
    body = invitation.json()
    assert body["email"] == "recruiter@example.com"
    assert body["role"] == "member"
    token = _token(body)

    preview = await client.get(f"/api/v1/team/invitations/{token}")
    assert preview.status_code == 200
    assert preview.json()["company_name"] == "Acme Coffee"

    # The raw bearer token is never persisted.
    async with TestSession() as db:
        stored = await db.scalar(select(TeamInvitation))
        assert stored is not None
        assert stored.token_hash != token
        assert len(stored.token_hash) == 64

    wrong_user = await register(client, "wrong@example.com")
    wrong_accept = await client.post(
        f"/api/v1/team/invitations/{token}/accept", headers=wrong_user["headers"]
    )
    assert wrong_accept.status_code == 403

    member = await register(client, "recruiter@example.com")
    accepted = await client.post(
        f"/api/v1/team/invitations/{token}/accept", headers=member["headers"]
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["company_id"] == owner["company_id"]

    team = await client.get("/api/v1/company/team", headers=owner["headers"])
    assert {row["email"]: row["role"] for row in team.json()} == {
        "recruiter@example.com": "member",
        owner["email"]: "owner",
    }
    assert all(row["joined_at"] for row in team.json())

    reused = await client.post(
        f"/api/v1/team/invitations/{token}/accept", headers=member["headers"]
    )
    assert reused.status_code == 410


async def test_resend_rotates_link_and_revoke_invalidates_it(client):
    owner = await make_company(client)
    first = await client.post(
        "/api/v1/company/team/invitations",
        json={"email": "member@example.com"},
        headers=owner["headers"],
    )
    second = await client.post(
        "/api/v1/company/team/invitations",
        json={"email": "member@example.com"},
        headers=owner["headers"],
    )
    first_token, second_token = _token(first.json()), _token(second.json())
    assert first_token != second_token
    assert (await client.get(f"/api/v1/team/invitations/{first_token}")).status_code == 404
    assert (await client.get(f"/api/v1/team/invitations/{second_token}")).status_code == 200

    pending = await client.get(
        "/api/v1/company/team/invitations", headers=owner["headers"]
    )
    assert len(pending.json()) == 1

    revoked = await client.delete(
        f"/api/v1/company/team/invitations/{second.json()['id']}",
        headers=owner["headers"],
    )
    assert revoked.status_code == 204
    assert (await client.get(f"/api/v1/team/invitations/{second_token}")).status_code == 404


async def test_member_is_blocked_from_owner_settings_and_can_be_removed(client):
    owner = await make_company(client)
    member, _ = await _invite_and_accept(client, owner)

    assert (
        await client.post(
            "/api/v1/company/team/invitations",
            json={"email": "another@example.com"},
            headers=member["headers"],
        )
    ).status_code == 403
    assert (
        await client.patch(
            "/api/v1/company", json={"name": "Hijacked"}, headers=member["headers"]
        )
    ).status_code == 403
    assert (
        await client.get("/api/v1/billing/summary", headers=member["headers"])
    ).status_code == 403
    assert (await client.get("/api/v1/bot", headers=member["headers"])).status_code == 403

    team = (await client.get("/api/v1/company/team", headers=owner["headers"])).json()
    member_id = next(row["user_id"] for row in team if row["role"] == "member")
    removed = await client.delete(
        f"/api/v1/company/team/{member_id}", headers=owner["headers"]
    )
    assert removed.status_code == 204
    assert (await client.get("/api/v1/company", headers=member["headers"])).status_code == 403


async def test_owner_can_transfer_ownership(client):
    owner = await make_company(client)
    member, _ = await _invite_and_accept(client, owner)
    team = (await client.get("/api/v1/company/team", headers=owner["headers"])).json()
    member_id = next(row["user_id"] for row in team if row["role"] == "member")

    transferred = await client.post(
        f"/api/v1/company/team/{member_id}/transfer-ownership",
        headers=owner["headers"],
    )
    assert transferred.status_code == 200, transferred.text
    roles = {row["email"]: row["role"] for row in transferred.json()}
    assert roles[member["email"]] == "owner"
    assert roles[owner["email"]] == "member"

    old_owner_invite = await client.post(
        "/api/v1/company/team/invitations",
        json={"email": "new@example.com"},
        headers=owner["headers"],
    )
    assert old_owner_invite.status_code == 403
    new_owner_invite = await client.post(
        "/api/v1/company/team/invitations",
        json={"email": "new@example.com"},
        headers=member["headers"],
    )
    assert new_owner_invite.status_code == 201
