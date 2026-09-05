"""Bulk placement replacement and in-place course swapping."""

from __future__ import annotations


def _snapshot(detail: dict) -> set[tuple[str, int]]:
    return {(p["course"]["code"], p["term_index"]) for p in detail["placements"]}


def _restore(account, placements):
    return account.client.put(
        f"/api/plans/{account.default_plan_id}/placements",
        json={"placements": placements},
        headers=account.headers,
    )


def test_replacing_placements_sets_the_plan_exactly(account):
    account.place("CIS 1100", 0)
    account.place("CIS 1200", 1)

    wanted = [
        {"course_id": account.course_id("CIS 1600"), "term_index": 0},
        {"course_id": account.course_id("MATH 1400"), "term_index": 3},
    ]
    detail = _restore(account, wanted).json()
    assert _snapshot(detail) == {("CIS 1600", 0), ("MATH 1400", 3)}


def test_replacing_with_an_empty_list_clears_the_plan(account):
    account.place("CIS 1100", 0)
    detail = _restore(account, []).json()
    assert detail["placements"] == []
    assert detail["total_planned_credits"] == 0


def test_a_snapshot_round_trip_restores_a_plan_exactly(account):
    """This is what undo relies on, so it gets an explicit test."""
    account.client.post(
        f"/api/plans/{account.default_plan_id}/autofill", headers=account.headers
    )
    before = account.client.get(
        f"/api/plans/{account.default_plan_id}", headers=account.headers
    ).json()
    snapshot = [
        {"course_id": p["course_id"], "term_index": p["term_index"]}
        for p in before["placements"]
    ]

    _restore(account, [])
    cleared = account.client.get(
        f"/api/plans/{account.default_plan_id}", headers=account.headers
    ).json()
    assert cleared["placements"] == []

    after = _restore(account, snapshot).json()
    assert _snapshot(after) == _snapshot(before)
    assert after["total_planned_credits"] == before["total_planned_credits"]
    assert after["diagnostics"] == before["diagnostics"]


def test_the_same_course_twice_in_one_request_is_rejected(account):
    course_id = account.course_id("CIS 1200")
    response = _restore(
        account,
        [{"course_id": course_id, "term_index": 0}, {"course_id": course_id, "term_index": 1}],
    )
    assert response.status_code == 422


def test_an_unknown_course_id_rejects_the_whole_request(account):
    account.place("CIS 1100", 0)
    response = _restore(
        account,
        [
            {"course_id": account.course_id("CIS 1200"), "term_index": 0},
            {"course_id": 987654, "term_index": 1},
        ],
    )
    assert response.status_code == 404

    # Nothing was applied, so the original placement is still there.
    detail = account.client.get(
        f"/api/plans/{account.default_plan_id}", headers=account.headers
    ).json()
    assert _snapshot(detail) == {("CIS 1100", 0)}


def test_an_out_of_range_term_rejects_the_whole_request(account):
    response = _restore(
        account, [{"course_id": account.course_id("CIS 1200"), "term_index": 12}]
    )
    assert response.status_code == 422


def test_replacing_placements_is_scoped_to_the_owner(account, other_account):
    response = account.client.put(
        f"/api/plans/{other_account.default_plan_id}/placements",
        json={"placements": []},
        headers=account.headers,
    )
    assert response.status_code == 404


def _swap(account, code, replacement_code):
    return account.client.post(
        f"/api/plans/{account.default_plan_id}/courses/{account.course_id(code)}/swap",
        json={"replacement_course_id": account.course_id(replacement_code)},
        headers=account.headers,
    )


def test_swapping_a_placeholder_keeps_the_term(account):
    account.place("TECH-1", 5)
    detail = _swap(account, "TECH-1", "CIS 5550").json()
    assert _snapshot(detail) == {("CIS 5550", 5)}


def test_swapping_preserves_the_rest_of_the_plan(account):
    account.place("CIS 1200", 0)
    account.place("TECH-1", 5)
    detail = _swap(account, "TECH-1", "CIS 5450").json()
    assert ("CIS 1200", 0) in _snapshot(detail)
    assert ("CIS 5450", 5) in _snapshot(detail)


def test_swapping_in_a_course_already_planned_is_a_conflict(account):
    account.place("CIS 5450", 4)
    account.place("TECH-1", 5)
    response = _swap(account, "TECH-1", "CIS 5450")
    assert response.status_code == 409
    assert "already in this plan" in response.json()["detail"]


def test_swapping_a_course_for_itself_is_rejected(account):
    account.place("TECH-1", 5)
    response = _swap(account, "TECH-1", "TECH-1")
    assert response.status_code == 422


def test_swapping_something_not_in_the_plan_is_a_404(account):
    response = _swap(account, "TECH-1", "CIS 5450")
    assert response.status_code == 404


def test_swapping_revalidates_the_plan(account):
    # CIS 4500 needs CIS 1210 and CIS 1600, neither of which is planned, so
    # swapping it into a slot has to surface that immediately.
    account.place("TECH-1", 5)
    detail = _swap(account, "TECH-1", "CIS 4500").json()
    problems = [
        d for d in detail["diagnostics"]
        if d["severity"] == "error" and d["course_code"] == "CIS 4500"
    ]
    assert problems


def test_swapping_is_scoped_to_the_owner(account, other_account):
    other_account.place("TECH-1", 5)
    response = account.client.post(
        f"/api/plans/{other_account.default_plan_id}"
        f"/courses/{account.course_id('TECH-1')}/swap",
        json={"replacement_course_id": account.course_id("CIS 5450")},
        headers=account.headers,
    )
    assert response.status_code == 404
