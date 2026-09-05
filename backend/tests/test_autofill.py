"""The automatic scheduler."""

from __future__ import annotations


def _fill(account):
    response = account.client.post(
        f"/api/plans/{account.default_plan_id}/autofill", headers=account.headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def _errors(detail: dict) -> list[dict]:
    return [d for d in detail["diagnostics"] if d["severity"] == "error"]


def test_autofill_produces_a_plan_with_no_prerequisite_errors(account):
    detail = _fill(account)
    assert _errors(detail) == [], _errors(detail)


def test_autofill_schedules_every_core_course(account):
    detail = _fill(account)
    codes = {p["course"]["code"] for p in detail["placements"]}
    core = {
        "CIS 1100", "CIS 1200", "CIS 1210", "CIS 2400",
        "CIS 2620", "CIS 3200", "CIS 4480", "CIS 4710", "CIS 4000",
    }
    assert core <= codes


def test_autofill_keeps_every_term_within_the_full_time_range(account):
    detail = _fill(account)
    for term in detail["terms"]:
        # Between the full-time minimum and the overload threshold, so a
        # generated plan produces no load warnings at all.
        assert 4.0 <= term["credits"] <= 5.5, term


def test_autofill_starts_the_long_prerequisite_chains_early(account):
    # The point of ordering by critical path: the courses that gate the most
    # other courses have to open the plan, not drift into the third year.
    detail = _fill(account)
    term_of = {p["course"]["code"]: p["term_index"] for p in detail["placements"]}
    assert term_of["CIS 1200"] == 0
    assert term_of["CIS 1600"] == 0
    assert term_of["CIS 1210"] <= 1
    assert term_of["CIS 2400"] <= 2
    assert term_of["CIS 3200"] <= 4


def test_autofill_puts_the_introductory_course_in_the_first_term(account):
    # CIS 1100 has no catalog prerequisite tying it to CIS 1200, so nothing in
    # the prerequisite graph would place it first. The advising preference does.
    detail = _fill(account)
    term_of = {p["course"]["code"]: p["term_index"] for p in detail["placements"]}
    assert term_of["CIS 1100"] == 0
    assert term_of["CIS 1100"] <= term_of["CIS 1200"]


def test_an_advising_preference_never_becomes_an_error(account):
    # Placing CIS 1100 late is unusual but entirely legal, so it must not raise.
    detail = account.place("CIS 1100", 5).json()
    assert [d for d in detail["diagnostics"] if d["course_code"] == "CIS 1100"] == []


def test_autofill_respects_senior_standing(account):
    detail = _fill(account)
    term_of = {p["course"]["code"]: p["term_index"] for p in detail["placements"]}
    assert term_of["CIS 4000"] >= 6


def test_autofill_orders_the_core_sequence_correctly(account):
    detail = _fill(account)
    term_of = {p["course"]["code"]: p["term_index"] for p in detail["placements"]}
    assert term_of["CIS 1200"] < term_of["CIS 1210"]
    assert term_of["CIS 1600"] < term_of["CIS 1210"]
    assert term_of["CIS 1210"] < term_of["CIS 3200"]
    assert term_of["CIS 2620"] < term_of["CIS 3200"]
    assert term_of["CIS 2400"] < term_of["CIS 4480"]
    assert term_of["CIS 2400"] < term_of["CIS 4710"]


def test_autofill_does_not_move_what_the_student_already_placed(account):
    account.place("CIS 1200", 2)
    detail = _fill(account)
    term_of = {p["course"]["code"]: p["term_index"] for p in detail["placements"]}
    assert term_of["CIS 1200"] == 2
    assert term_of["CIS 1210"] > 2


def test_running_autofill_twice_adds_nothing_the_second_time(account):
    first = _fill(account)
    second = _fill(account)
    assert len(second["placements"]) == len(first["placements"])
    assert {(p["course"]["code"], p["term_index"]) for p in second["placements"]} == {
        (p["course"]["code"], p["term_index"]) for p in first["placements"]
    }


def test_autofill_covers_the_full_degree(account):
    detail = _fill(account)
    audit = detail["audit"]
    assert audit["complete"] is True
    assert audit["satisfied_count"] == audit["requirement_count"]
    # Every requirement filled means the matched credits equal the degree.
    assert audit["credits_matched"] == detail["required_credits"] == 37.0


def test_autofill_works_for_every_seeded_program(account):
    """The scheduler is program-driven, so it has to hold for all ten.

    This is the test that would have caught the corequisite cycle in the
    mechanical engineering data, which blocked six requirements and which no
    computer science plan ever touches.
    """
    for code in account.programs():
        plan = account.new_plan(code, name=code)
        detail = account.autofill(plan["id"])
        audit = detail["audit"]
        problems = [d for d in detail["diagnostics"] if d["severity"] != "info"]
        assert audit["complete"] is True, f"{code} did not complete"
        assert problems == [], f"{code} produced {problems}"


def test_autofill_only_touches_the_callers_own_plan(account, other_account):
    victim = other_account.default_plan_id
    response = account.client.post(
        f"/api/plans/{victim}/autofill", headers=account.headers
    )
    assert response.status_code == 404
    untouched = other_account.client.get(
        f"/api/plans/{victim}", headers=other_account.headers
    ).json()
    assert untouched["placements"] == []
