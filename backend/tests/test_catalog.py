"""Branches, vacancies and questions: CRUD, ordering, duplication, reassignment."""

from tests.conftest import make_company


async def _branch(client, owner, name="Чиланзар", city="Ташкент", **kw):
    resp = await client.post(
        "/api/v1/branches", json={"name": name, "city": city, **kw}, headers=owner["headers"]
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _vacancy(client, owner, title="Бариста", **kw):
    resp = await client.post(
        "/api/v1/vacancies", json={"title": title, **kw}, headers=owner["headers"]
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_first_active_branch_enables_branch_mode(client):
    owner = await make_company(client)
    assert owner["company"]["branches_enabled"] is False

    await _branch(client, owner)
    company = await client.get("/api/v1/company", headers=owner["headers"])
    assert company.json()["branches_enabled"] is True


async def test_hidden_branch_does_not_enable_branch_mode(client):
    owner = await make_company(client)
    await _branch(client, owner, is_active=False)
    company = await client.get("/api/v1/company", headers=owner["headers"])
    assert company.json()["branches_enabled"] is False


async def test_enabling_branch_mode_without_branches_is_rejected(client):
    owner = await make_company(client)
    resp = await client.patch(
        "/api/v1/company", json={"branches_enabled": True}, headers=owner["headers"]
    )
    assert resp.status_code == 422


async def test_branch_reorder(client):
    owner = await make_company(client)
    a = await _branch(client, owner, "A")
    b = await _branch(client, owner, "B")
    c = await _branch(client, owner, "C")

    resp = await client.post(
        "/api/v1/branches/reorder",
        json={"ids": [c["id"], a["id"], b["id"]]},
        headers=owner["headers"],
    )
    assert resp.status_code == 204

    listing = await client.get("/api/v1/branches", headers=owner["headers"])
    assert [x["name"] for x in listing.json()] == ["C", "A", "B"]


async def test_reorder_rejects_foreign_ids(client):
    owner = await make_company(client)
    other = await make_company(client, "Other")
    foreign = await _branch(client, other, "Foreign")

    resp = await client.post(
        "/api/v1/branches/reorder", json={"ids": [foreign["id"]]}, headers=owner["headers"]
    )
    assert resp.status_code == 404


async def test_delete_branch_moves_vacancies(client):
    owner = await make_company(client)
    source = await _branch(client, owner, "Source")
    target = await _branch(client, owner, "Target")
    vacancy = await _vacancy(client, owner, branch_id=source["id"])

    resp = await client.delete(
        f"/api/v1/branches/{source['id']}?move_vacancies_to={target['id']}",
        headers=owner["headers"],
    )
    assert resp.status_code == 204

    moved = await client.get(f"/api/v1/vacancies/{vacancy['id']}", headers=owner["headers"])
    assert moved.json()["branch_id"] == target["id"]


async def test_delete_branch_detaches_vacancies_by_default(client):
    owner = await make_company(client)
    branch = await _branch(client, owner)
    vacancy = await _vacancy(client, owner, branch_id=branch["id"])

    resp = await client.delete(f"/api/v1/branches/{branch['id']}", headers=owner["headers"])
    assert resp.status_code == 204

    detached = await client.get(f"/api/v1/vacancies/{vacancy['id']}", headers=owner["headers"])
    assert detached.json()["branch_id"] is None


async def test_cannot_move_vacancies_into_another_tenants_branch(client):
    owner = await make_company(client)
    attacker_target = await _branch(client, await make_company(client, "Other"), "Foreign")
    branch = await _branch(client, owner)

    resp = await client.delete(
        f"/api/v1/branches/{branch['id']}?move_vacancies_to={attacker_target['id']}",
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_vacancy_filter_by_branch(client):
    owner = await make_company(client)
    branch = await _branch(client, owner)
    await _vacancy(client, owner, "In branch", branch_id=branch["id"])
    await _vacancy(client, owner, "General")

    in_branch = await client.get(
        f"/api/v1/vacancies?branch_id={branch['id']}", headers=owner["headers"]
    )
    assert [v["title"] for v in in_branch.json()] == ["In branch"]

    general = await client.get("/api/v1/vacancies?branch_id=null", headers=owner["headers"])
    assert [v["title"] for v in general.json()] == ["General"]


async def test_duplicate_copies_questions_into_another_branch(client):
    owner = await make_company(client)
    branch_a = await _branch(client, owner, "A")
    branch_b = await _branch(client, owner, "B")
    vacancy = await _vacancy(client, owner, branch_id=branch_a["id"])

    for text in ("Ваш опыт?", "Когда готовы выйти?"):
        resp = await client.post(
            "/api/v1/questions",
            json={"text": text, "type": "short_text", "vacancy_id": vacancy["id"]},
            headers=owner["headers"],
        )
        assert resp.status_code == 201, resp.text

    dup = await client.post(
        f"/api/v1/vacancies/{vacancy['id']}/duplicate",
        json={"branch_id": branch_b["id"]},
        headers=owner["headers"],
    )
    assert dup.status_code == 201
    copy = dup.json()
    assert copy["branch_id"] == branch_b["id"]
    # A copy must never go live unreviewed.
    assert copy["status"] == "draft"

    copied_questions = await client.get(
        f"/api/v1/questions?vacancy_id={copy['id']}", headers=owner["headers"]
    )
    assert [q["text"] for q in copied_questions.json()] == ["Ваш опыт?", "Когда готовы выйти?"]


async def test_choice_question_requires_two_to_ten_options(client):
    owner = await make_company(client)

    too_few = await client.post(
        "/api/v1/questions",
        json={"text": "Смена?", "type": "single_choice", "options": ["Утро"]},
        headers=owner["headers"],
    )
    assert too_few.status_code == 422

    too_many = await client.post(
        "/api/v1/questions",
        json={"text": "Смена?", "type": "single_choice", "options": [str(i) for i in range(11)]},
        headers=owner["headers"],
    )
    assert too_many.status_code == 422

    ok = await client.post(
        "/api/v1/questions",
        json={"text": "Смена?", "type": "single_choice", "options": ["Утро", "Вечер"]},
        headers=owner["headers"],
    )
    assert ok.status_code == 201


async def test_number_validation_range_is_checked(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/questions",
        json={"text": "Возраст", "type": "number", "validation": {"min": 40, "max": 18}},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_salary_range_is_validated(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/vacancies",
        json={"title": "Бариста", "salary_from": 9_000_000, "salary_to": 3_000_000},
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_deep_link_absent_without_bot(client):
    owner = await make_company(client)
    vacancy = await _vacancy(client, owner)
    assert vacancy["deep_link"] is None
