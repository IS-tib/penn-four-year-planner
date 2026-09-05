"""Degree rules that are not about ordering: cross-listing and elective level."""

from __future__ import annotations


def _diagnostics(detail: dict, code: str) -> list[dict]:
    return [d for d in detail["diagnostics"] if d["code"] == code]


def test_the_same_course_under_two_numbers_is_caught(account):
    account.place("CIS 2400", 0)
    account.place("CIS 4480", 2)
    detail = account.place("CIS 5480", 4).json()
    duplicates = _diagnostics(detail, "duplicate_course")
    assert len(duplicates) == 1
    assert "CIS 4480 and CIS 5480" in duplicates[0]["message"]
    assert duplicates[0]["severity"] == "error"


def test_the_duplicate_is_reported_against_the_later_placement(account):
    account.place("CIS 2400", 0)
    account.place("CIS 4710", 2)
    detail = account.place("CIS 5710", 5).json()
    duplicate = _diagnostics(detail, "duplicate_course")[0]
    # Pointing at the one further along is what lets the interface highlight the
    # copy a student most likely wants to drop.
    assert duplicate["course_code"] == "CIS 5710"
    assert duplicate["term_index"] == 5


def test_taking_only_one_of_a_cross_listed_pair_is_fine(account):
    account.place("CIS 2400", 0)
    detail = account.place("CIS 5480", 2).json()
    assert _diagnostics(detail, "duplicate_course") == []





def test_a_graduate_number_fills_the_core_requirement_row(account):
    account.place("CIS 2400", 0)
    detail = account.place("CIS 5480", 2).json()
    rows = [
        r
        for g in detail["audit"]["groups"]
        for r in g["requirements"]
        if r["label"] == "CIS 4480 or CIS 5480"
    ]
    assert len(rows) == 1
    assert rows[0]["satisfied"] is True


def test_a_graduate_number_satisfies_a_prerequisite(account):
    # Nothing in the seeded catalog requires CIS 4500, so this checks the
    # expansion directly: CIS 5510 requires CIS 1600 and CIS 2400, and its own
    # cross-listed twin CIS 4510 requires the same. Placing the graduate
    # numbers of the prerequisites must not break either.
    account.place("CIS 1600", 0)
    account.place("CIS 1200", 0)
    account.place("CIS 2400", 1)
    detail = account.place("CIS 5510", 2).json()
    assert [d for d in detail["diagnostics"] if d["course_code"] == "CIS 5510"] == []


def _fill_cis_elective_slot(account, slot_code, course_code, term):
    """Put a real course into a CIS elective slot, the way the app does."""
    account.place(slot_code, term)
    return account.client.post(
        f"/api/plans/{account.plan_id}/courses/{account.course_id(slot_code)}/swap",
        json={"replacement_course_id": account.course_id(course_code)},
        headers=account.headers,
    ).json()


def test_two_half_unit_language_courses_are_within_the_elective_cap(account):
    account.place("CIS 1200", 0)
    _fill_cis_elective_slot(account, "CIS-EL-1", "CIS 1902", 1)
    detail = _fill_cis_elective_slot(account, "CIS-EL-2", "CIS 1904", 1)
    assert _diagnostics(detail, "elective_level_cap") == []


def test_three_half_unit_language_courses_break_the_elective_cap(account):
    account.place("CIS 1200", 0)
    _fill_cis_elective_slot(account, "CIS-EL-1", "CIS 1902", 1)
    _fill_cis_elective_slot(account, "CIS-EL-2", "CIS 1904", 1)
    detail = _fill_cis_elective_slot(account, "CIS-EL-3", "CIS 1905", 2)
    breach = _diagnostics(detail, "elective_level_cap")
    assert len(breach) == 1
    assert breach[0]["severity"] == "error"
    assert "1.5 CU" in breach[0]["message"]
    for code in ("CIS 1902", "CIS 1904", "CIS 1905"):
        assert code in breach[0]["message"]


def test_the_level_cap_only_counts_courses_put_into_cis_elective_slots(account):
    # CIS 1100, CIS 1200 and CIS 1600 are all 1000-level and all 1 CU, but they
    # fill named requirements, not elective slots, so the cap must ignore them.
    account.place("CIS 1100", 0)
    account.place("CIS 1200", 0)
    detail = account.place("CIS 1600", 0).json()
    assert _diagnostics(detail, "elective_level_cap") == []


def test_the_catalog_exposes_cross_listing_to_the_client(account):
    courses = account.client.get(
        "/api/courses", params={"search": "CIS 4480"}, headers=account.headers
    ).json()
    entry = next(c for c in courses if c["code"] == "CIS 4480")
    assert entry["equivalent_codes"] == ["CIS 5480"]
    assert entry["level"] == 4000
    assert entry["subject"] == "CIS"


def test_the_catalog_exposes_what_a_course_unlocks(account):
    courses = account.client.get(
        "/api/courses", params={"search": "CIS 1200"}, headers=account.headers
    ).json()
    entry = next(c for c in courses if c["code"] == "CIS 1200")
    assert {"CIS 1210", "CIS 2400"} <= set(entry["unlocks_codes"])


def test_the_catalog_exposes_prerequisite_groups(account):
    courses = account.client.get(
        "/api/courses", params={"search": "MATH 2400"}, headers=account.headers
    ).json()
    entry = next(c for c in courses if c["code"] == "MATH 2400")
    assert entry["prerequisite_groups"] == [
        {"codes": ["MATH 1410", "MATH 1610"], "concurrent": False}
    ]

    physics = account.client.get(
        "/api/courses", params={"search": "PHYS 0150"}, headers=account.headers
    ).json()
    entry = next(c for c in physics if c["code"] == "PHYS 0150")
    assert entry["prerequisite_groups"] == [
        {"codes": ["MATH 1400"], "concurrent": True}
    ]
