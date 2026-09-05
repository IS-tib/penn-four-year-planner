"""Assembling the API view of a plan.

Every plan mutation returns the whole recomputed plan, diagnostics included,
rather than just the row that changed. It costs one extra query and it removes
a whole class of bug: the client cannot hold a stale idea of whether the plan
is valid, because it never computes validity itself.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..models import Course, Plan, Prerequisite
from .planner import (
    CourseInfo,
    DegreeAudit,
    PlanValidator,
    PrereqGroup,
    equivalence_map,
    term_label,
)


def load_courses(db: Session) -> dict[int, CourseInfo]:
    rows = db.execute(select(Course)).scalars().all()
    return {
        row.id: CourseInfo(
            id=row.id,
            code=row.code,
            title=row.title,
            credits=row.credits,
            category=row.category,
            min_term_index=row.min_term_index,
            level=row.level,
            equivalence_key=row.equivalence_key,
        )
        for row in rows
    }


def load_dependents(prereqs: dict[int, list[PrereqGroup]]) -> dict[int, list[int]]:
    """Reverse the prerequisite graph: course id to the ids it unlocks.

    The interface uses this to answer "what does taking this open up", which is
    the question a student actually asks when deciding between two electives.
    """
    dependents: dict[int, set[int]] = defaultdict(set)
    for course_id, groups in prereqs.items():
        for group in groups:
            for required_id in group.required_ids:
                dependents[required_id].add(course_id)
    return {course_id: sorted(ids) for course_id, ids in dependents.items()}


def load_prerequisites(db: Session) -> dict[int, list[PrereqGroup]]:
    grouped: dict[int, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    concurrent: dict[tuple[int, int], bool] = {}
    for row in db.execute(select(Prerequisite)).scalars().all():
        grouped[row.course_id][row.group_index].append(row.required_course_id)
        # allow_concurrent is a property of the group; it is stored per row, so
        # a group counts as concurrent if any of its rows says so.
        key = (row.course_id, row.group_index)
        concurrent[key] = concurrent.get(key, False) or row.allow_concurrent

    return {
        course_id: [
            PrereqGroup(
                required_ids=tuple(sorted(members)),
                allow_concurrent=concurrent[(course_id, group_index)],
            )
            for group_index, members in sorted(groups.items())
        ]
        for course_id, groups in grouped.items()
    }


def prerequisite_text(groups: list[PrereqGroup], courses: dict[int, CourseInfo]) -> str:
    """Render CNF groups back into readable form, e.g. "CIS 1200 and CIS 1600"."""
    if not groups:
        return ""
    parts: list[str] = []
    for group in groups:
        codes = [courses[i].code for i in group.required_ids if i in courses]
        if not codes:
            continue
        rendered = codes[0] if len(codes) == 1 else "(" + " or ".join(codes) + ")"
        if group.allow_concurrent:
            rendered += " (may be concurrent)"
        parts.append(rendered)
    return " and ".join(parts)


def prerequisite_codes(groups: list[PrereqGroup], courses: dict[int, CourseInfo]) -> list[str]:
    codes: list[str] = []
    for group in groups:
        for course_id in group.required_ids:
            info = courses.get(course_id)
            if info is not None and info.code not in codes:
                codes.append(info.code)
    return codes


def serialize_plan(db: Session, plan: Plan) -> dict:
    courses = load_courses(db)
    prereqs = load_prerequisites(db)

    placements_rows = (
        db.execute(
            select(Plan)
            .where(Plan.id == plan.id)
            .options(selectinload(Plan.placements))
        )
        .scalars()
        .one()
        .placements
    )
    placements = {row.course_id: row.term_index for row in placements_rows}

    validator = PlanValidator(courses, prereqs, plan.start_year)
    audit = DegreeAudit(courses)
    diagnostics = validator.validate(placements)

    by_term: dict[int, list[int]] = {i: [] for i in range(settings.terms_per_plan)}
    for course_id, term in placements.items():
        by_term.setdefault(term, []).append(course_id)

    terms = []
    for index in range(settings.terms_per_plan):
        ids = sorted(by_term.get(index, []), key=lambda cid: courses[cid].code)
        terms.append(
            {
                "index": index,
                "label": term_label(plan.start_year, index),
                "credits": round(sum(courses[cid].credits for cid in ids), 2),
                "course_ids": ids,
            }
        )

    course_rows = {row.id: row for row in db.execute(select(Course)).scalars().all()}
    dependents = load_dependents(prereqs)
    equivalents = equivalence_map(courses)
    serialized_placements = [
        {
            "course_id": course_id,
            "term_index": term,
            "course": course_payload(
                course_rows[course_id], prereqs, courses, dependents, equivalents
            ),
        }
        for course_id, term in sorted(placements.items(), key=lambda kv: (kv[1], kv[0]))
    ]

    return {
        "id": plan.id,
        "name": plan.name,
        "start_year": plan.start_year,
        "share_token": plan.share_token,
        "terms": terms,
        "placements": serialized_placements,
        "diagnostics": [vars(d) for d in diagnostics],
        "progress": [vars(p) for p in audit.progress(placements)],
        "total_planned_credits": audit.total_planned(placements),
        "degree_total_credits": audit.degree_total,
        "published_degree_credits": audit.published_degree_total,
    }


def course_payload(
    course: Course,
    prereqs: dict[int, list[PrereqGroup]],
    courses: dict[int, CourseInfo],
    dependents: dict[int, list[int]] | None = None,
    equivalents: dict[int, set[int]] | None = None,
) -> dict:
    groups = prereqs.get(course.id, [])
    unlocks = (dependents or {}).get(course.id, [])
    twins = sorted((equivalents or {}).get(course.id, ()))
    return {
        "id": course.id,
        "code": course.code,
        "title": course.title,
        "credits": course.credits,
        "department": course.department,
        "category": course.category,
        "description": course.description or "",
        "is_placeholder": course.is_placeholder,
        "level": course.level,
        "min_term_index": course.min_term_index,
        "prerequisite_text": prerequisite_text(groups, courses),
        "prerequisite_codes": prerequisite_codes(groups, courses),
        # The groups, not just the flattened codes, so the browser can work out
        # for itself which terms a course could legally go in while it is being
        # dragged. That is a hint for the cursor; the server still decides.
        "prerequisite_groups": [
            {
                "codes": [courses[i].code for i in group.required_ids if i in courses],
                "concurrent": group.allow_concurrent,
            }
            for group in groups
        ],
        "unlocks_codes": [courses[i].code for i in unlocks if i in courses],
        "equivalent_codes": [courses[i].code for i in twins if i in courses],
    }
