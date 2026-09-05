"""The degree audit, which is a matching rather than a sum."""

from __future__ import annotations

import pytest


def _rows(detail: dict) -> dict[str, dict]:
    return {
        r["label"]: r
        for g in detail["audit"]["groups"]
        for r in g["requirements"]
    }


def test_programs_are_public_so_the_landing_page_can_list_them(client):
    response = client.get("/api/programs")
    assert response.status_code == 200
    programs = response.json()
    assert len(programs) == 10
    assert {p["school_code"] for p in programs} == {"SEAS", "COLLEGE"}
    assert all(p["source_url"].startswith("https://catalog.upenn.edu") for p in programs)


def test_every_seas_degree_totals_the_published_thirty_seven(client):
    for program in client.get("/api/programs").json():
        if program["school_code"] == "SEAS":
            assert program["total_units"] == 37.0, program["code"]


def test_a_program_detail_lists_its_requirement_groups(client):
    detail = client.get("/api/programs/CIS-BSE").json()
    names = [group["name"] for group in detail["groups"]]
    assert "Engineering" in names
    assert "Math and Natural Science" in names
    total = sum(group["credits"] for group in detail["groups"])
    assert total == detail["total_units"] == 37.0


def test_an_unknown_program_is_a_404(client):
    assert client.get("/api/programs/NOPE-BSE").status_code == 404


def test_a_course_fills_the_requirement_that_names_it(account):
    detail = account.place("CIS 1200", 0).json()
    rows = _rows(detail)
    assert rows["CIS 1200"]["satisfied"] is True
    assert rows["CIS 1200"]["filled_slots"] == 1
    assert rows["CIS 1210"]["satisfied"] is False


def test_a_course_can_only_be_spent_once(account):
    """The whole reason the audit is a matching and not a sum.

    Biology's physical-sciences row accepts CIS 1200, and so does its own
    named requirement in Computer Science. Within one program a course must
    pay for one requirement only, which is what Penn's own footnote says.
    """
    plan = account.new_plan("BIOL-BA", name="Bio")
    account.place("CIS 1200", 0, plan_id=plan["id"])
    account.place("CIS 1600", 0, plan_id=plan["id"])
    detail = account.plan(plan["id"])
    audit = detail["audit"]
    # Two courses placed, so at most two requirement slots can be filled.
    filled = sum(r["filled_slots"] for g in audit["groups"] for r in g["requirements"])
    assert filled == 2
    assert audit["credits_matched"] == 2.0


def test_the_matching_reassigns_rather_than_giving_up(account):
    """A greedy first-come assignment would report this plan incomplete.

    CIS 4480 can fill the operating systems core row. So can CIS 5480. If the
    first course grabs a row the second one also needs and never yields it, one
    row goes unfilled. Augmenting paths move the earlier course aside.
    """
    plan = account.new_plan("CIS-BA", name="Second major")
    for code in ("CIS 1100", "CIS 1200", "CIS 1600", "CIS 1210", "CIS 2400"):
        account.place(code, 0, plan_id=plan["id"])
    detail = account.plan(plan["id"])
    audit = detail["audit"]
    # Every one of the five is doing a job, none is stranded.
    assert audit["unassigned_course_ids"] == []
    assert audit["credits_matched"] == 5.0


def test_a_course_the_program_does_not_want_is_reported_unassigned(account):
    # FNAR 0010 is a Digital Media Design requirement and nothing in the
    # Computer Science degree accepts it.
    detail = account.place("FNAR 0010", 0).json()
    audit = detail["audit"]
    assert audit["unassigned_course_ids"] == [account.course_id("FNAR 0010")]
    assert audit["credits_matched"] == 0.0
    assert audit["credits_planned"] == 1.0


def test_a_slot_placeholder_cannot_satisfy_a_named_requirement(account):
    detail = account.place("TECH-1", 0).json()
    rows = _rows(detail)
    assert rows["CIS 1200"]["satisfied"] is False
    assert rows["Technical Elective"]["filled_slots"] == 1


def test_a_real_course_only_fills_an_open_row_once_chosen_for_it(account):
    """The catalog never prints which courses count as humanities.

    So an arbitrary course does not silently satisfy that row. It counts once
    the student puts it there, which the swap flow records.
    """
    account.place("CIS 3500", 0)
    rows = _rows(account.plan())
    assert rows["Technical Elective"]["filled_slots"] == 0

    account.place("TECH-1", 1)
    account.client.post(
        f"/api/plans/{account.plan_id}/courses/{account.course_id('TECH-1')}/swap",
        json={"replacement_course_id": account.course_id("CIS 3900")},
        headers=account.headers,
    )
    rows = _rows(account.plan())
    assert rows["Technical Elective"]["filled_slots"] == 1


def test_a_multi_slot_row_counts_up_to_its_capacity(account):
    for index, term in ((1, 0), (2, 0), (3, 1)):
        account.place(f"SSH-{index}", term)
    rows = _rows(account.plan())
    row = rows["Social Science or Humanities"]
    assert row["slots"] == 4
    assert row["filled_slots"] == 3
    assert row["satisfied"] is False


@pytest.mark.parametrize("code", ["CIS-BSE", "BE-BSE", "MEAM-BSE", "BIOL-BA", "MATH-BA"])
def test_an_empty_plan_satisfies_nothing_and_errs_at_nothing(account, code):
    detail = account.new_plan(code, name=code)
    assert detail["audit"]["satisfied_count"] == 0
    assert [d for d in detail["diagnostics"] if d["severity"] == "error"] == []


def test_a_second_major_does_not_get_full_time_load_warnings(account):
    """Twelve course units over eight terms is not an underloaded plan.

    It is a second major, and the student is taking other things alongside it.
    """
    plan = account.new_plan("CIS-BA", name="Second major")
    account.place("CIS 1100", 0, plan_id=plan["id"])
    detail = account.plan(plan["id"])
    assert detail["program"]["tracks_full_degree"] is False
    assert [d for d in detail["diagnostics"] if d["code"] == "term_underload"] == []


def test_a_full_degree_still_gets_load_warnings(account):
    account.place("CIS 1100", 0)
    detail = account.plan()
    assert [d for d in detail["diagnostics"] if d["code"] == "term_underload"]


# --------------------------------------------------------------- relevance --
def _relevant_codes(account, detail: dict) -> set[str]:
    catalog = account.client.get("/api/courses", headers=account.headers).json()
    by_id = {course["id"]: course for course in catalog}
    return {by_id[cid]["code"] for cid in detail["relevant_course_ids"] if cid in by_id}


def test_the_catalog_filter_names_only_courses_this_degree_accepts(account):
    """The sidebar's degree filter is driven by the matcher, not by subject.

    A subject filter would be a guess: MATH 1400 belongs to no engineering
    subject and counts toward every SEAS degree, while plenty of CIS courses
    below the elective floor count toward none.
    """
    codes = _relevant_codes(account, account.plan())
    assert "CIS 1200" in codes  # named outright by the CS BSE requirement table
    assert "MATH 1400" in codes  # a different subject, still required
    assert "CIS 3200" in codes  # matched by the CIS elective pattern
    assert "BE 2200" not in codes  # a Bioengineering course CS never accepts
    assert "TECH-1" in codes  # this degree's own technical elective slot
    assert "GENED-1" not in codes  # a College slot no SEAS degree uses
    assert 0 < len(codes) < 80  # a browsable list, not the whole catalog


def test_relevance_is_per_degree_not_global(client):
    from .conftest import Account

    cs = Account(client, "cs.student@upenn.edu", program="CIS-BSE")
    be = Account(client, "be.student@upenn.edu", program="BE-BSE")
    cs_codes = _relevant_codes(cs, cs.plan())
    be_codes = _relevant_codes(be, be.plan())
    assert cs_codes != be_codes
    assert "BE 2200" in be_codes and "BE 2200" not in cs_codes
    # Both degrees share the same first-year mathematics, so the two sets are
    # different without being disjoint.
    assert "MATH 1400" in cs_codes and "MATH 1400" in be_codes


def test_only_this_degree_s_own_requirement_slots_are_relevant(account):
    """Slots are numbered per requirement across all ten programs.

    Seventy-five of them exist. A Computer Science student has business with
    about twenty, and scrolling past the other fifty-five is exactly the wall
    this filter is for.
    """
    catalog = account.client.get("/api/courses", headers=account.headers).json()
    slots = {course["code"] for course in catalog if course["is_slot"]}
    relevant = _relevant_codes(account, account.plan()) & slots
    assert len(slots) > 60  # the fixture would be vacuous otherwise
    assert relevant < slots
    assert {"TECH-1", "CIS-EL-1", "SSH-1"} <= relevant
    assert not relevant & {"GENED-1", "MATH-ADV-1", "BE-EL-1"}
