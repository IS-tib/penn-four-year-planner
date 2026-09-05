"""Assembling the API view of a plan.

Every plan mutation returns the whole recomputed plan, diagnostics and degree
audit included, rather than just the row that changed. It costs a couple of
extra queries and it removes a class of bug: the client cannot hold a stale
idea of whether the plan is valid, because it never computes validity itself.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..models import Course, Plan, PlanCourse, Prerequisite, Program, Requirement
from .audit import DegreeAudit, build_requirement_views
from .planner import (
    CourseInfo,
    PlanValidator,
    PrereqGroup,
    coverage_diagnostic,
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
            subject=row.subject,
            level=row.level,
            is_slot=row.is_slot,
            slot_tag=row.slot_tag,
            min_term_index=row.min_term_index,
            equivalence_key=row.equivalence_key,
        )
        for row in rows
    }


def load_prerequisites(db: Session) -> dict[int, list[PrereqGroup]]:
    grouped: dict[int, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    concurrent: dict[tuple[int, int], bool] = {}
    for row in db.execute(select(Prerequisite)).scalars().all():
        grouped[row.course_id][row.group_index].append(row.required_course_id)
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


def load_dependents(prereqs: dict[int, list[PrereqGroup]]) -> dict[int, list[int]]:
    """Reverse the prerequisite graph: course id to the ids it unlocks."""
    dependents: dict[int, set[int]] = defaultdict(set)
    for course_id, groups in prereqs.items():
        for group in groups:
            for required_id in group.required_ids:
                dependents[required_id].add(course_id)
    return {course_id: sorted(ids) for course_id, ids in dependents.items()}


def prerequisite_text(groups: list[PrereqGroup], courses: dict[int, CourseInfo]) -> str:
    """Render CNF groups back into readable form, e.g. "CIS 1200 and CIS 1600"."""
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
        "subject": course.subject,
        "description": course.description or "",
        "is_slot": course.is_slot,
        "slot_tag": course.slot_tag,
        "level": course.level,
        "min_term_index": course.min_term_index,
        "prerequisite_text": prerequisite_text(groups, courses),
        "prerequisite_codes": [
            courses[i].code
            for group in groups
            for i in group.required_ids
            if i in courses
        ],
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


def program_payload(program: Program, include_requirements: bool = False) -> dict:
    payload = {
        "id": program.id,
        "code": program.code,
        "name": program.name,
        "degree": program.degree,
        "school": program.school.name,
        "school_code": program.school.code,
        "total_units": program.total_units,
        "term_count": program.term_count,
        "tracks_full_degree": program.tracks_full_degree,
        "notes": program.notes or "",
        "source_url": program.source_url or "",
    }
    if include_requirements:
        payload["groups"] = [
            {
                "name": group.name,
                "notes": group.notes or "",
                "credits": round(sum(r.credits for r in group.requirements), 2),
                "requirements": [
                    {
                        "id": r.id,
                        "label": r.label,
                        "credits": r.credits,
                        "slots": r.slots,
                        "match_kind": r.match_kind,
                        "slot_tag": r.slot_tag,
                        "notes": r.notes or "",
                        "option_codes": sorted(o.course.code for o in r.options),
                    }
                    for r in group.requirements
                ],
            }
            for group in program.groups
        ]
    return payload


def serialize_plan(db: Session, plan: Plan) -> dict:
    courses = load_courses(db)
    prereqs = load_prerequisites(db)
    equivalents = equivalence_map(courses)
    dependents = load_dependents(prereqs)

    rows = (
        db.execute(select(PlanCourse).where(PlanCourse.plan_id == plan.id))
        .scalars()
        .all()
    )
    placements = {row.course_id: row.term_index for row in rows}
    designations = {row.course_id: row.fills_slot_tag for row in rows if row.fills_slot_tag}

    program = plan.program
    term_count = program.term_count

    validator = PlanValidator(
        courses, prereqs, plan.start_year, term_count,
        check_term_load=program.tracks_full_degree,
    )
    diagnostics = validator.validate(placements, designations)

    requirements = build_requirement_views(program)
    engine = DegreeAudit(requirements, courses, equivalents)
    audit = engine.run(list(placements), designations)
    diagnostics.extend(coverage_diagnostic(audit, plan.start_year))

    # Which of the two hundred odd catalog entries this degree has any use for.
    # A Computer Science student opening the catalog on Bioengineering courses,
    # then scrolling past twenty other degrees' requirement slots, is not a
    # small annoyance: it is the difference between a browsable list and a wall.
    #
    # The matcher answers it directly, so no second rule has to be invented and
    # kept in step. Note what that excludes: a real course is not relevant to an
    # open slot unless the student designated it, because the catalog never
    # prints which courses count as humanities and guessing would be inventing a
    # rule Penn does not publish.
    relevant_course_ids = sorted(
        course_id for course_id in courses if engine.edges_for(course_id)
    )

    by_term: dict[int, list[int]] = {i: [] for i in range(term_count)}
    for course_id, term in placements.items():
        by_term.setdefault(term, []).append(course_id)

    terms = []
    for index in range(term_count):
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
    serialized_placements = [
        {
            "course_id": row.course_id,
            "term_index": row.term_index,
            "fills_slot_tag": row.fills_slot_tag,
            "course": course_payload(
                course_rows[row.course_id], prereqs, courses, dependents, equivalents
            ),
        }
        for row in sorted(rows, key=lambda r: (r.term_index, r.course_id))
    ]

    return {
        "id": plan.id,
        "name": plan.name,
        "start_year": plan.start_year,
        "share_token": plan.share_token,
        "program": program_payload(program),
        "terms": terms,
        "placements": serialized_placements,
        "diagnostics": [vars(d) for d in diagnostics],
        "audit": audit_payload(audit),
        "relevant_course_ids": relevant_course_ids,
        "total_planned_credits": audit.credits_planned,
        "required_credits": program.total_units or audit.credits_required,
    }


def audit_payload(audit) -> dict:
    """Group the flat matching result back into the catalog's own headings."""
    groups: list[dict] = []
    for row in audit.requirements:
        requirement = row.requirement
        if not groups or groups[-1]["position"] != requirement.group_position:
            groups.append(
                {
                    "position": requirement.group_position,
                    "name": requirement.group_name,
                    "notes": requirement.group_notes,
                    "requirements": [],
                }
            )
        groups[-1]["requirements"].append(
            {
                "id": requirement.id,
                "label": requirement.label,
                "credits": requirement.credits,
                "slots": requirement.slots,
                "filled_slots": row.filled_slots,
                "satisfied": row.satisfied,
                "match_kind": requirement.match_kind,
                "slot_tag": requirement.slot_tag,
                "notes": requirement.notes,
                "matched_course_ids": row.matched,
            }
        )
    for group in groups:
        group["credits"] = round(
            sum(r["credits"] for r in group["requirements"]), 2
        )
        group["satisfied"] = all(r["satisfied"] for r in group["requirements"])
    return {
        "groups": groups,
        "complete": audit.complete,
        "satisfied_count": audit.satisfied_count,
        "requirement_count": len(audit.requirements),
        "credits_required": audit.credits_required,
        "credits_matched": audit.credits_matched,
        "credits_planned": audit.credits_planned,
        "unassigned_course_ids": audit.unassigned,
    }
