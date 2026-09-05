"""Plan mutation and the authorization boundary between accounts."""

from __future__ import annotations

from sqlalchemy import select

from app.models import PlanCourse


def _codes(detail: dict) -> set[str]:
    return {placement["course"]["code"] for placement in detail["placements"]}


def test_placing_a_course_returns_the_whole_plan(account):
    response = account.place("CIS 1200", 0)
    assert response.status_code == 201
    detail = response.json()
    assert _codes(detail) == {"CIS 1200"}
    assert detail["terms"][0]["credits"] == 1.0
    assert "diagnostics" in detail and "audit" in detail


def test_a_course_cannot_be_placed_twice_in_one_plan(account):
    assert account.place("CIS 1200", 0).status_code == 201
    duplicate = account.place("CIS 1200", 3)
    assert duplicate.status_code == 409
    assert "already in this plan" in duplicate.json()["detail"]


def test_moving_a_course_changes_its_term(account):
    account.place("CIS 1200", 0)
    course_id = account.course_id("CIS 1200")
    response = account.client.patch(
        f"/api/plans/{account.default_plan_id}/courses/{course_id}",
        json={"term_index": 2},
        headers=account.headers,
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["terms"][0]["credits"] == 0
    assert detail["terms"][2]["credits"] == 1.0


def test_removing_a_course_empties_the_term(account):
    account.place("CIS 1200", 0)
    course_id = account.course_id("CIS 1200")
    response = account.client.delete(
        f"/api/plans/{account.default_plan_id}/courses/{course_id}", headers=account.headers
    )
    assert response.status_code == 200
    assert _codes(response.json()) == set()


def test_moving_a_course_that_is_not_in_the_plan_is_a_404(account):
    course_id = account.course_id("CIS 1200")
    response = account.client.patch(
        f"/api/plans/{account.default_plan_id}/courses/{course_id}",
        json={"term_index": 1},
        headers=account.headers,
    )
    assert response.status_code == 404


def test_an_unknown_course_id_is_a_404(account):
    response = account.client.post(
        f"/api/plans/{account.default_plan_id}/courses",
        json={"course_id": 999999, "term_index": 0},
        headers=account.headers,
    )
    assert response.status_code == 404


def test_a_term_outside_the_eight_semesters_is_rejected(account):
    course_id = account.course_id("CIS 1200")
    for bad_term in (-1, 8, 99):
        response = account.client.post(
            f"/api/plans/{account.default_plan_id}/courses",
            json={"course_id": course_id, "term_index": bad_term},
            headers=account.headers,
        )
        assert response.status_code == 422, bad_term


def test_one_account_cannot_read_another_accounts_plan(account, other_account):
    victim_plan = other_account.default_plan_id
    response = account.client.get(f"/api/plans/{victim_plan}", headers=account.headers)
    # 404 rather than 403, so the response does not confirm the plan exists.
    assert response.status_code == 404


def test_one_account_cannot_write_to_another_accounts_plan(account, other_account):
    victim_plan = other_account.default_plan_id
    course_id = account.course_id("CIS 1200")
    write = account.client.post(
        f"/api/plans/{victim_plan}/courses",
        json={"course_id": course_id, "term_index": 0},
        headers=account.headers,
    )
    assert write.status_code == 404

    delete = account.client.delete(f"/api/plans/{victim_plan}", headers=account.headers)
    assert delete.status_code == 404

    still_there = other_account.client.get(
        f"/api/plans/{victim_plan}", headers=other_account.headers
    )
    assert still_there.status_code == 200


def test_creating_and_renaming_a_plan(account):
    created = account.client.post(
        "/api/plans",
        json={
            "program_id": account.program("CIS-BSE")["id"],
            "name": "Backup plan",
            "start_year": 2026,
        },
        headers=account.headers,
    )
    assert created.status_code == 201
    plan_id = created.json()["id"]

    renamed = account.client.patch(
        f"/api/plans/{plan_id}", json={"name": "Plan B"}, headers=account.headers
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Plan B"


def test_deleting_a_plan_removes_its_placements(account, db):
    account.place("CIS 1200", 0)
    plan_id = account.default_plan_id
    assert account.client.delete(f"/api/plans/{plan_id}", headers=account.headers).status_code == 204

    orphans = db.execute(
        select(PlanCourse).where(PlanCourse.plan_id == plan_id)
    ).scalars().all()
    assert orphans == []


def test_term_labels_follow_the_start_year(account):
    created = account.new_plan(name="Class of 2030")
    labels = [term["label"] for term in created["terms"]]
    assert labels == [
        "Fall 2026", "Spring 2027",
        "Fall 2027", "Spring 2028",
        "Fall 2028", "Spring 2029",
        "Fall 2029", "Spring 2030",
    ]


def test_catalog_search_matches_code_and_title(account):
    by_code = account.client.get(
        "/api/courses", params={"search": "CIS 12"}, headers=account.headers
    ).json()
    assert [c["code"] for c in by_code] == ["CIS 1200", "CIS 1210"]

    by_title = account.client.get(
        "/api/courses", params={"search": "algorithms"}, headers=account.headers
    ).json()
    assert "CIS 3200" in {c["code"] for c in by_title}


def test_catalog_exposes_readable_prerequisites(account):
    courses = account.client.get(
        "/api/courses", params={"search": "MATH 2400"}, headers=account.headers
    ).json()
    entry = next(c for c in courses if c["code"] == "MATH 2400")
    # MATH 2400's catalog prerequisite is "MATH 1410 OR MATH 1610".
    assert entry["prerequisite_text"] == "(MATH 1410 or MATH 1610)"
    assert set(entry["prerequisite_codes"]) == {"MATH 1410", "MATH 1610"}
