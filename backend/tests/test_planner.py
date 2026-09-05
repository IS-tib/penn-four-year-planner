"""Prerequisite and course-load rules, tested through the API."""

from __future__ import annotations


def _diagnostics(detail: dict, code: str) -> list[dict]:
    return [d for d in detail["diagnostics"] if d["code"] == code]


def _errors(detail: dict) -> list[dict]:
    return [d for d in detail["diagnostics"] if d["severity"] == "error"]


def test_a_course_with_no_prerequisites_scheduled_is_flagged(account):
    detail = account.place("CIS 1210", 0).json()
    missing = _diagnostics(detail, "missing_prerequisite")
    mentioned = {d["message"] for d in missing}
    assert any("CIS 1200" in m for m in mentioned)
    assert any("CIS 1600" in m for m in mentioned)


def test_a_prerequisite_in_the_same_term_is_too_late(account):
    account.place("CIS 1200", 0)
    account.place("CIS 1600", 0)
    detail = account.place("CIS 1210", 0).json()
    out_of_order = _diagnostics(detail, "prerequisite_out_of_order")
    assert len(out_of_order) == 2
    assert all(d["course_code"] == "CIS 1210" for d in out_of_order)


def test_prerequisites_in_an_earlier_term_satisfy_the_rule(account):
    account.place("CIS 1200", 0)
    account.place("CIS 1600", 0)
    detail = account.place("CIS 1210", 1).json()
    assert _diagnostics(detail, "prerequisite_out_of_order") == []
    assert _diagnostics(detail, "missing_prerequisite") == []


def test_an_or_group_is_satisfied_by_either_option(account):
    # MATH 2400 requires MATH 1410 OR MATH 1610. Either alone is enough.
    account.place("MATH 1610", 0)
    detail = account.place("MATH 2400", 1).json()
    assert [d for d in _errors(detail) if d["course_code"] == "MATH 2400"] == []


def test_an_or_group_reports_both_options_when_neither_is_planned(account):
    detail = account.place("MATH 2400", 2).json()
    message = next(
        d["message"] for d in _diagnostics(detail, "missing_prerequisite")
        if d["course_code"] == "MATH 2400"
    )
    assert "MATH 1410 or MATH 1610" in message


def test_a_concurrent_prerequisite_may_share_a_term(account):
    # The catalog lets PHYS 0150 be taken alongside MATH 1400.
    account.place("MATH 1400", 0)
    detail = account.place("PHYS 0150", 0).json()
    assert [d for d in _errors(detail) if d["course_code"] == "PHYS 0150"] == []


def test_a_concurrent_prerequisite_still_cannot_come_later(account):
    account.place("MATH 1400", 3)
    detail = account.place("PHYS 0150", 1).json()
    assert _diagnostics(detail, "prerequisite_out_of_order")


def test_a_term_over_the_credit_cap_warns(account):
    for index, code in enumerate(["CIS 1100", "CIS 1200", "CIS 1600", "MATH 1400"]):
        account.place(code, 0)
    account.place("PHYS 0150", 0)  # 1.5 CU, bringing the term to 5.5
    detail = account.place("CIS 1962", 0).json()  # 0.5 CU, now 6.0
    overload = _diagnostics(detail, "term_overload")
    assert len(overload) == 1
    assert overload[0]["term_index"] == 0
    assert overload[0]["severity"] == "warning"


def test_a_term_at_exactly_the_cap_does_not_warn(account):
    for code in ["CIS 1100", "CIS 1200", "CIS 1600", "MATH 1400"]:
        account.place(code, 0)
    detail = account.place("PHYS 0150", 0).json()  # exactly 5.5
    assert detail["terms"][0]["credits"] == 5.5
    assert _diagnostics(detail, "term_overload") == []


def test_a_thin_term_warns_but_an_empty_one_does_not(account):
    detail = account.place("CIS 1100", 0).json()
    underload = _diagnostics(detail, "term_underload")
    assert [d["term_index"] for d in underload] == [0]


def test_the_audit_reports_what_a_plan_has_filled(account):
    account.place("CIS 1100", 0)
    detail = account.place("MATH 1400", 0).json()
    audit = detail["audit"]
    assert audit["credits_planned"] == 2.0
    assert audit["credits_matched"] == 2.0
    assert audit["satisfied_count"] == 2
    assert audit["complete"] is False
    assert detail["required_credits"] == 37.0


def test_outstanding_requirements_are_summarised(account):
    detail = account.place("CIS 1100", 0).json()
    notes = _diagnostics(detail, "requirements_outstanding")
    assert len(notes) == 1
    assert notes[0]["severity"] == "info"
    assert "not yet filled" in notes[0]["message"]


def test_a_senior_standing_course_cannot_sit_in_the_first_year(account):
    detail = account.place("CIS 4000", 1).json()
    standing = _diagnostics(detail, "standing_requirement")
    assert len(standing) == 1
    assert standing[0]["severity"] == "error"
    assert "senior standing" in standing[0]["message"]


def test_a_senior_standing_course_is_fine_in_the_fourth_year(account):
    detail = account.place("CIS 4000", 6).json()
    assert _diagnostics(detail, "standing_requirement") == []


def test_an_empty_plan_has_no_errors(account):
    detail = account.client.get(
        f"/api/plans/{account.default_plan_id}", headers=account.headers
    ).json()
    assert _errors(detail) == []
