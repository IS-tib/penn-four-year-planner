"""Load schools, courses, slots and degree programs into the database.

Runs on every startup and is idempotent: rows are matched by their natural key
and updated in place, so editing the catalog files and restarting is enough to
change the data and no plan loses its placements.

The seeder also refuses to start on bad data. Three checks run before anything
commits, because each of these mistakes would otherwise produce an app that is
quietly and confidently wrong rather than obviously broken:

- a program whose requirement rows do not add up to the total the catalog prints
- an equivalence key grouping courses that are not plausibly the same course
- a requirement naming a course that is not in the catalog
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import COURSES, PROGRAMS, SCHOOLS, SLOT_TAGS
from .models import (
    MATCH_EXPLICIT,
    MATCH_PATTERN,
    MATCH_SLOT,
    Course,
    Prerequisite,
    Program,
    Requirement,
    RequirementGroup,
    RequirementOption,
    School,
)

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]


class SeedError(RuntimeError):
    """Raised when the catalog data is internally inconsistent."""


# --------------------------------------------------------------------------
# Validation, run before anything is written
# --------------------------------------------------------------------------


def _slot_demand() -> dict[str, tuple[int, float]]:
    """How many of each slot any single program needs, and what each is worth.

    A tag used with two different credit values would make a slot worth
    different amounts depending on the degree, which is not a thing, so it is
    rejected rather than silently resolved.
    """
    demand: dict[str, tuple[int, float]] = {}
    for program in PROGRAMS:
        per_program: dict[str, int] = {}
        for group in program["groups"]:
            for row in group["rows"]:
                if row["kind"] != "slot":
                    continue
                tag = row["tag"]
                each = round(row["credits"] / row["slots"], 4)
                per_program[tag] = per_program.get(tag, 0) + row["slots"]
                known = demand.get(tag)
                if known is not None and known[1] != each:
                    raise SeedError(
                        f"Slot {tag!r} is worth {known[1]} course units in one "
                        f"program and {each} in {program['code']}."
                    )
                demand[tag] = (max(known[0] if known else 0, per_program[tag]), each)
        for tag, count in per_program.items():
            demand[tag] = (max(demand[tag][0], count), demand[tag][1])
    unknown = set(demand) - set(SLOT_TAGS)
    if unknown:
        raise SeedError(f"Slot tags used but not named: {sorted(unknown)}")
    return demand


def _check_totals() -> None:
    for program in PROGRAMS:
        if program["total_units"] is None:
            continue
        total = round(
            sum(row["credits"] for group in program["groups"] for row in group["rows"]), 2
        )
        if total != program["total_units"]:
            raise SeedError(
                f"{program['code']} rows add up to {total} course units but the "
                f"catalog prints {program['total_units']}. One of the two is a "
                "transcription error and it needs fixing, not rounding away."
            )


def _check_equivalences() -> None:
    """Two courses sharing an equivalence key must plausibly be one course.

    The authority is the catalog's own "Mutually Exclusive" line. This checks
    the structural consequence of that: cross-listed pairs share the last three
    digits of their number, or print the same title. A typo here would silently
    reject a legitimate plan, which is worse than refusing to start.
    """
    by_key: dict[str, list[dict]] = {}
    for entry in COURSES:
        if entry["equiv"]:
            by_key.setdefault(entry["equiv"], []).append(entry)

    for key, entries in by_key.items():
        if len(entries) < 2:
            raise SeedError(f"Equivalence key {key!r} groups only one course.")
        titles = {e["title"] for e in entries}
        suffixes = {e["code"].split()[-1][-3:] for e in entries}
        if len(titles) > 1 and len(suffixes) > 1:
            codes = ", ".join(sorted(e["code"] for e in entries))
            raise SeedError(
                f"Equivalence key {key!r} groups {codes}, which share neither a "
                f"title nor a course number suffix: {sorted(titles)}"
            )


def _check_requirement_courses() -> None:
    known = {entry["code"] for entry in COURSES}
    for program in PROGRAMS:
        for group in program["groups"]:
            for row in group["rows"]:
                for code in row.get("codes", []):
                    if code not in known:
                        raise SeedError(
                            f"{program['code']} requires {code}, which is not in "
                            "the course catalog."
                        )


def validate_catalog() -> dict[str, tuple[int, float]]:
    _check_totals()
    _check_equivalences()
    _check_requirement_courses()
    return _slot_demand()


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def _upsert_courses(db: Session, slot_demand: dict[str, tuple[int, float]]) -> None:
    existing = {course.code: course for course in db.execute(select(Course)).scalars()}

    for entry in COURSES:
        course = existing.get(entry["code"]) or Course(code=entry["code"])
        if course.id is None:
            db.add(course)
        course.title = entry["title"]
        course.credits = entry["credits"]
        course.subject = entry["subject"]
        course.description = entry["description"]
        course.level = entry["level"]
        course.equivalence_key = entry["equiv"]
        course.min_term_index = entry["min_term"]
        course.preferred_term = entry["preferred_term"]
        course.is_slot = False
        course.slot_tag = None

    # Slots are generated rather than written by hand, because how many of each
    # are needed is a property of the programs, not something to keep in sync.
    for tag, (count, each) in sorted(slot_demand.items()):
        for index in range(1, count + 1):
            code = f"{tag.upper()}-{index}"
            course = existing.get(code) or Course(code=code)
            if course.id is None:
                db.add(course)
            numeral = ROMAN[index - 1] if index <= len(ROMAN) else str(index)
            course.title = f"{SLOT_TAGS[tag]} {numeral}" if count > 1 else SLOT_TAGS[tag]
            course.credits = each
            course.subject = "SLOT"
            course.description = (
                "A requirement the catalog leaves open. Resolve it into a real "
                "course once you have chosen one."
            )
            course.level = None
            course.equivalence_key = None
            course.min_term_index = 0
            course.preferred_term = None
            course.is_slot = True
            course.slot_tag = tag
    db.flush()


def _rebuild_prerequisites(db: Session) -> None:
    by_code = {course.code: course for course in db.execute(select(Course)).scalars()}

    for row in db.execute(select(Prerequisite)).scalars():
        db.delete(row)
    db.flush()

    for entry in COURSES:
        course = by_code[entry["code"]]
        for group_index, group in enumerate(entry["prereqs"]):
            for code in group["any_of"]:
                required = by_code.get(code)
                if required is None:
                    raise SeedError(
                        f"{entry['code']} lists prerequisite {code}, which is not "
                        "in the catalog."
                    )
                db.add(
                    Prerequisite(
                        course_id=course.id,
                        group_index=group_index,
                        required_course_id=required.id,
                        allow_concurrent=bool(group.get("concurrent", False)),
                    )
                )
    db.flush()


def _rebuild_programs(db: Session) -> None:
    by_code = {course.code: course for course in db.execute(select(Course)).scalars()}
    schools = {s.code: s for s in db.execute(select(School)).scalars()}

    for entry in SCHOOLS:
        school = schools.get(entry["code"]) or School(code=entry["code"])
        if school.id is None:
            db.add(school)
        school.name = entry["name"]
    db.flush()
    schools = {s.code: s for s in db.execute(select(School)).scalars()}

    existing = {p.code: p for p in db.execute(select(Program)).scalars()}
    for entry in PROGRAMS:
        program = existing.get(entry["code"]) or Program(code=entry["code"])
        if program.id is None:
            db.add(program)
        program.name = entry["name"]
        program.degree = entry["degree"]
        program.school_id = schools[entry["school"]].id
        program.total_units = entry["total_units"]
        program.notes = entry["notes"]
        program.tracks_full_degree = entry.get("full_degree", True)
        program.source_url = entry["source"]
        db.flush()

        # Requirements are rebuilt wholesale. They carry no user data, so there
        # is nothing to preserve, and rebuilding avoids having to diff them.
        for group in list(program.groups):
            db.delete(group)
        db.flush()

        for position, group_entry in enumerate(entry["groups"]):
            group = RequirementGroup(
                program_id=program.id,
                position=position,
                name=group_entry["name"],
                notes=group_entry.get("note", ""),
            )
            db.add(group)
            db.flush()

            for row_position, row in enumerate(group_entry["rows"]):
                requirement = Requirement(
                    group_id=group.id,
                    position=row_position,
                    label=row["label"],
                    credits=row["credits"],
                    slots=row["slots"],
                    notes=row.get("note", ""),
                )
                if row["kind"] == "explicit":
                    requirement.match_kind = MATCH_EXPLICIT
                elif row["kind"] == "pattern":
                    requirement.match_kind = MATCH_PATTERN
                    requirement.pattern_subjects = ",".join(row["subjects"])
                    requirement.pattern_min_level = row["min_level"]
                else:
                    requirement.match_kind = MATCH_SLOT
                    requirement.slot_tag = row["tag"]
                db.add(requirement)
                db.flush()

                for code in row.get("codes", []):
                    db.add(
                        RequirementOption(
                            requirement_id=requirement.id, course_id=by_code[code].id
                        )
                    )
    db.flush()


def seed_catalog(db: Session) -> None:
    slot_demand = validate_catalog()
    _upsert_courses(db, slot_demand)
    _rebuild_prerequisites(db)
    _rebuild_programs(db)
    db.commit()
