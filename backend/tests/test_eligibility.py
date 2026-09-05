"""What a student can legally take in a given term."""

from __future__ import annotations


def _eligible(account, term, **params):
    response = account.client.get(
        f"/api/plans/{account.default_plan_id}/eligible",
        params={"term_index": term, **params},
        headers=account.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _codes(rows) -> set[str]:
    return {row["code"] for row in rows}


def test_a_gated_course_is_not_offered_until_its_prerequisites_are_planned(account):
    assert "CIS 1210" not in _codes(_eligible(account, 0))
    assert "CIS 1200" in _codes(_eligible(account, 0))


def test_a_course_becomes_eligible_once_its_prerequisites_are_early_enough(account):
    account.place("CIS 1200", 0)
    account.place("CIS 1600", 0)
    assert "CIS 1210" not in _codes(_eligible(account, 0))
    assert "CIS 1210" in _codes(_eligible(account, 1))


def test_a_concurrent_prerequisite_makes_a_course_eligible_in_the_same_term(account):
    account.place("MATH 1400", 2)
    assert "PHYS 0150" in _codes(_eligible(account, 2))


def test_courses_already_in_the_plan_are_not_offered_again(account):
    account.place("CIS 1200", 0)
    assert "CIS 1200" not in _codes(_eligible(account, 3))


def test_the_cross_listed_twin_of_a_planned_course_is_not_offered(account):
    account.place("CIS 2400", 0)
    account.place("CIS 4480", 2)
    offered = _codes(_eligible(account, 4))
    assert "CIS 5480" not in offered, "offering the twin would create a duplicate"


def test_a_senior_standing_course_is_only_offered_in_the_fourth_year(account):
    assert "CIS 4000" not in _codes(_eligible(account, 3))
    assert "CIS 4000" in _codes(_eligible(account, 6))


def test_results_lead_with_what_the_degree_still_needs(account):
    rows = _eligible(account, 0, exclude_slots=True)
    fitting = [row for row in rows if not row["would_overload"]]
    # Courses that fill an outstanding requirement come first, and within that
    # group the ones that unlock the most come first.
    needed = [row for row in fitting if row["counts_toward"]]
    assert needed, "nothing was flagged as counting toward a requirement"
    assert fitting[: len(needed)] == needed
    unlocks = [row["unlocks"] for row in needed]
    assert unlocks == sorted(unlocks, reverse=True)
    # With ten programs seeded, MATH 1400 sits above more of the catalog than
    # CIS 1200 does, so the leader is whichever genuinely unlocks the most.
    assert needed[0]["unlocks"] >= 10
    assert {"CIS 1200", "MATH 1400"} <= {row["code"] for row in needed[:5]}


def test_courses_that_would_overload_the_term_are_flagged_and_sorted_last(account):
    for code in ["CIS 1100", "CIS 1200", "CIS 1600", "MATH 1400"]:
        account.place(code, 0)
    account.place("PHYS 0150", 0)  # the term is now at the 5.5 CU limit

    rows = _eligible(account, 0)
    assert rows, "a full term should still offer courses, just flagged"
    assert all(row["would_overload"] for row in rows)

    # A half-unit course would also overload a term already at the cap.
    half = next(row for row in rows if row["credits"] == 0.5)
    assert half["would_overload"] is True


def test_filtering_by_subject(account):
    rows = _eligible(account, 4, subject="MATH")
    assert rows
    assert {row["subject"] for row in rows} == {"MATH"}


def test_filtering_to_one_kind_of_slot(account):
    rows = _eligible(account, 4, slot_tag="ssh")
    assert rows
    assert all(row["is_slot"] for row in rows)
    assert all(row["code"].startswith("SSH-") for row in rows)


def test_slots_can_be_excluded(account):
    with_slots = _eligible(account, 4)
    without = _eligible(account, 4, exclude_slots=True)
    assert any(row["is_slot"] for row in with_slots)
    assert not any(row["is_slot"] for row in without)


def test_eligibility_agrees_with_validation(account):
    """Anything offered for a term must validate cleanly when placed there.

    The finder walks the rules forwards and the validator walks them backwards,
    so this is the test that keeps the two implementations honest about each
    other.
    """
    account.place("CIS 1200", 0)
    account.place("CIS 1600", 0)
    account.place("MATH 1400", 0)

    offered = _eligible(account, 2, exclude_slots=True)
    assert len(offered) > 10

    for row in offered[:12]:
        detail = account.client.post(
            f"/api/plans/{account.default_plan_id}/courses",
            json={"course_id": row["course_id"], "term_index": 2},
            headers=account.headers,
        ).json()
        blamed = [
            d for d in detail["diagnostics"]
            if d["severity"] == "error" and d["course_code"] == row["code"]
        ]
        assert blamed == [], f"{row['code']} was offered but does not validate: {blamed}"
        account.client.delete(
            f"/api/plans/{account.default_plan_id}/courses/{row['course_id']}",
            headers=account.headers,
        )


def test_eligibility_needs_a_valid_term(account):
    response = account.client.get(
        f"/api/plans/{account.default_plan_id}/eligible",
        params={"term_index": 99},
        headers=account.headers,
    )
    assert response.status_code == 422


def test_eligibility_is_scoped_to_the_owner(account, other_account):
    response = account.client.get(
        f"/api/plans/{other_account.default_plan_id}/eligible",
        params={"term_index": 0},
        headers=account.headers,
    )
    assert response.status_code == 404
