"""Switching majors: what carries over, what is wasted, how far behind."""

from __future__ import annotations


def _switch(account, target: str, plan_id: int | None = None) -> dict:
    response = account.client.get(
        f"/api/plans/{plan_id or account.plan_id}/switch/{target}", headers=account.headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def _codes(rows) -> set[str]:
    return {row["code"] for row in rows}


def test_switching_to_the_same_program_wastes_nothing(account):
    account.autofill()
    result = _switch(account, "CIS-BSE")
    assert result["wasted"] == []
    assert result["min_extra_terms"] == 0
    assert result["outstanding"] == 0
    assert "already in the plan" in result["verdict"]


def test_shared_courses_carry_over_between_engineering_degrees(account):
    # Computer Engineering and Computer Science share most of the CIS core.
    for code in ("CIS 1100", "CIS 1200", "CIS 1600", "MATH 1400"):
        account.place(code, 0)
    result = _switch(account, "CMPE-BSE")
    assert {"CIS 1100", "CIS 1200", "MATH 1400"} <= _codes(result["carried_over"])
    assert result["carried_credits"] >= 3.0


def test_a_course_the_target_does_not_want_is_wasted(account):
    # Mathematics BA has no use for a computer systems course.
    account.place("CIS 1200", 0)
    account.place("CIS 2400", 1)
    result = _switch(account, "MATH-BA")
    assert "CIS 2400" in _codes(result["wasted"])


def test_switching_far_afield_wastes_most_of_a_plan(account):
    account.autofill()
    result = _switch(account, "BIOL-BA")
    assert result["wasted_credits"] > result["carried_credits"]
    assert result["min_extra_terms"] >= 1
    assert "would no longer count" in result["verdict"]


def test_the_verdict_names_the_binding_constraint(account):
    account.autofill()
    result = _switch(account, "CMPE-BSE")
    reason = (
        "because of the course load"
        if result["extra_terms_from_load"] >= result["extra_terms_from_chain"]
        else "because of how long the prerequisite chains are"
    )
    assert reason in result["verdict"]


def test_the_estimate_is_the_larger_of_the_two_bounds(account):
    """Load and chain length limit progress independently.

    Spare capacity does not shorten a five-course prerequisite chain, and a
    short chain does not create room under the credit cap, so the honest
    answer is whichever binds harder.
    """
    account.autofill()
    for target in ("CMPE-BSE", "NETS-BSE", "BIOL-BA", "MATH-BA", "EE-BSE"):
        result = _switch(account, target)
        assert result["min_extra_terms"] == max(
            result["extra_terms_from_load"], result["extra_terms_from_chain"]
        ), target


def test_an_empty_plan_carries_nothing_and_needs_everything(account):
    result = _switch(account, "NETS-BSE")
    assert result["carried_over"] == []
    assert result["carried_credits"] == 0.0
    assert result["outstanding"] > 0
    assert result["remaining_credits"] > 30


def test_the_analysis_returns_the_target_programs_own_audit(account):
    account.autofill()
    result = _switch(account, "DMD-BSE")
    assert result["program"]["code"] == "DMD-BSE"
    labels = [
        r["label"] for g in result["audit"]["groups"] for r in g["requirements"]
    ]
    # A Digital Media Design row that Computer Science does not have.
    assert "CIS 4970" in labels


def test_switching_does_not_change_the_plan(account):
    account.autofill()
    before = account.plan()
    _switch(account, "BE-BSE")
    after = account.plan()
    assert before["placements"] == after["placements"]
    assert before["program"]["code"] == after["program"]["code"] == "CIS-BSE"


def test_every_pair_of_programs_can_be_compared(account):
    """Ten programs means ninety directed pairs, and none may blow up.

    Worth checking exhaustively because the chain-depth walk recurses over a
    prerequisite graph that contains corequisite cycles.
    """
    codes = list(account.programs())
    for source in codes:
        plan = account.new_plan(source, name=source)
        account.autofill(plan["id"])
        for target in codes:
            result = _switch(account, target, plan_id=plan["id"])
            assert result["min_extra_terms"] >= 0
            assert result["carried_credits"] >= 0
            assert isinstance(result["verdict"], str) and result["verdict"]


def test_an_unknown_target_program_is_a_404(account):
    response = account.client.get(
        f"/api/plans/{account.plan_id}/switch/NOPE-BSE", headers=account.headers
    )
    assert response.status_code == 404


def test_switch_analysis_is_scoped_to_the_owner(account, other_account):
    response = account.client.get(
        f"/api/plans/{other_account.plan_id}/switch/CIS-BSE", headers=account.headers
    )
    assert response.status_code == 404
