"""Load the course catalog into the database.

Runs on every startup and is idempotent: courses are matched by code and
updated in place, and each course's prerequisite rows are rebuilt from the
catalog file. Editing catalog.py and restarting is enough to change the data,
and no plan loses its placements because course ids are stable.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import COURSES
from .models import Course, Prerequisite


def seed_catalog(db: Session) -> None:
    existing = {course.code: course for course in db.execute(select(Course)).scalars()}

    for entry in COURSES:
        course = existing.get(entry["code"])
        if course is None:
            course = Course(code=entry["code"])
            db.add(course)
        course.title = entry["title"]
        course.credits = entry["credits"]
        course.department = entry["department"]
        course.category = entry["category"]
        course.description = entry["description"]
        course.is_placeholder = entry["placeholder"]
        course.min_term_index = entry["min_term"]
        course.preferred_term = entry["preferred_term"]
        course.level = entry["level"]
        course.equivalence_key = entry["equiv"]
    db.flush()

    by_code = {course.code: course for course in db.execute(select(Course)).scalars()}

    for entry in COURSES:
        course = by_code[entry["code"]]
        for row in db.execute(
            select(Prerequisite).where(Prerequisite.course_id == course.id)
        ).scalars():
            db.delete(row)
        db.flush()

        for group_index, group in enumerate(entry["prereqs"]):
            for code in group["any_of"]:
                required = by_code.get(code)
                if required is None:
                    raise ValueError(
                        f"{entry['code']} lists prerequisite {code}, which is not in the "
                        "catalog. Every prerequisite must itself be a seeded course."
                    )
                db.add(
                    Prerequisite(
                        course_id=course.id,
                        group_index=group_index,
                        required_course_id=required.id,
                        allow_concurrent=bool(group.get("concurrent", False)),
                    )
                )

    _check_equivalence_pairs()
    db.commit()


def _check_equivalence_pairs() -> None:
    """Guard the hand-written equivalence keys.

    Two courses sharing a key must share a title, because the key claims they
    are the same course under two numbers. A typo here would silently make the
    app reject a legitimate plan, which is worse than a crash at startup.
    """
    by_key: dict[str, list[dict]] = {}
    for entry in COURSES:
        if entry["equiv"]:
            by_key.setdefault(entry["equiv"], []).append(entry)

    for key, entries in by_key.items():
        titles = {entry["title"] for entry in entries}
        if len(titles) > 1:
            codes = ", ".join(sorted(entry["code"] for entry in entries))
            raise ValueError(
                f"Equivalence key {key!r} groups {codes}, but their titles differ: "
                f"{sorted(titles)}. Courses are only cross-listed if they are the "
                "same course."
            )
        if len(entries) < 2:
            raise ValueError(
                f"Equivalence key {key!r} has only one course. A key that groups "
                "nothing is a typo."
            )
