"""Fill the rest of a plan automatically.

Given whatever the student has already placed by hand, this drops every
remaining degree requirement into a term that keeps prerequisites in order and
keeps the load even. Existing placements are never moved, so the feature is
additive and a student cannot lose work by pressing it.

Two things make the output a schedule a person would actually follow rather
than merely a legal one.

Ordering is by critical path. The prerequisite relation is a DAG, and each
course is given a height: the length of the longest chain of courses that
depend on it. CIS 1200 has a high height because CIS 1210, CIS 3200 and the
systems courses all sit downstream of it, while a technical elective placeholder
has a height of zero. Scheduling by height descending puts the long chains into
the early terms and lets the free-floating electives fill whatever is left. A
plain topological order does not do this: it would happily hand the first term
to four electives and push CIS 1210 into third year, which is a valid plan and
a useless one.

Placement is balanced rather than earliest-fit. Each course goes into the first
term at or after its earliest legal term that is still under a soft target of
about one eighth of the degree. Only when no such term exists does it use the
headroom up to the real overload limit. Earliest-fit alone packs the first years
to the cap and leaves the last term empty.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import CORE, MNS
from ..config import settings
from ..models import Course, Plan, PlanCourse
from .plans import load_courses, load_prerequisites

# The math and science courses the autofill lays down. The degree allows
# several equivalent routes here (honors physics, different linear algebra
# options); this picks one standard route and the student can swap afterwards.
DEFAULT_MNS_TRACK = [
    "MATH 1400",
    "MATH 1410",
    "MATH 2400",
    "CIS 1600",
    "CIS 2610",
    "PHYS 0150",
    "PHYS 0151",
    "MNS-1",
]


def _target_courses(all_courses: list[Course]) -> list[Course]:
    by_code = {course.code: course for course in all_courses}
    targets: list[Course] = []
    seen: set[int] = set()
    claimed_keys: set[str] = set()

    def add(course: Course | None) -> None:
        if course is None or course.id in seen:
            return
        # CIS 4480 and CIS 5480 are one course, and both carry the core
        # category. Scheduling both would produce a plan that immediately
        # reports itself as double counting, so take whichever comes first.
        if course.equivalence_key:
            if course.equivalence_key in claimed_keys:
                return
            claimed_keys.add(course.equivalence_key)
        seen.add(course.id)
        targets.append(course)

    for course in all_courses:
        if course.category == CORE:
            add(course)
    for code in DEFAULT_MNS_TRACK:
        add(by_code.get(code))
    for course in all_courses:
        # Placeholder slots stand for the elective buckets, so filling them
        # completes the degree without pretending to choose electives for you.
        if course.is_placeholder and course.category != MNS:
            add(course)
    return targets


def _heights(targets: list[Course], prereqs) -> dict[int, int]:
    """Longest chain of dependents below each course, by memoized descent."""
    target_ids = {course.id for course in targets}
    dependents: dict[int, set[int]] = defaultdict(set)
    for course in targets:
        for group in prereqs.get(course.id, []):
            for required_id in group.required_ids:
                if required_id in target_ids:
                    dependents[required_id].add(course.id)

    height: dict[int, int] = {}
    visiting: set[int] = set()

    def compute(course_id: int) -> int:
        if course_id in height:
            return height[course_id]
        if course_id in visiting:
            # Only reachable if the seeded prerequisite data contains a cycle.
            return 0
        visiting.add(course_id)
        below = [compute(child) for child in dependents.get(course_id, ())]
        visiting.discard(course_id)
        height[course_id] = 1 + max(below) if below else 0
        return height[course_id]

    for course in targets:
        compute(course.id)
    return height


def _earliest_legal_term(course: Course, prereqs, placements: dict[int, int]) -> int | None:
    """The first term this course could legally sit in, or None if it cannot."""
    earliest = course.min_term_index
    for group in prereqs.get(course.id, []):
        scheduled = [placements[rid] for rid in group.required_ids if rid in placements]
        if not scheduled:
            # Nothing that satisfies this group is in the plan and nothing will
            # be, so the course has to stay out rather than be placed illegally.
            return None
        first = min(scheduled)
        earliest = max(earliest, first if group.allow_concurrent else first + 1)
    return earliest


def _choose_term(
    earliest: int,
    credits: float,
    load: list[float],
    terms: int,
    preferred: int | None = None,
) -> int | None:
    if (
        preferred is not None
        and earliest <= preferred < terms
        and load[preferred] + credits <= settings.max_term_credits
    ):
        return preferred
    for cap in (settings.balanced_term_credits, settings.max_term_credits):
        for term in range(earliest, terms):
            if load[term] + credits <= cap:
                return term
    return None


def autofill_plan(db: Session, plan: Plan, terms: int) -> None:
    all_courses = list(db.execute(select(Course)).scalars().all())
    prereqs = load_prerequisites(db)
    info = load_courses(db)

    existing = {
        row.course_id: row.term_index
        for row in db.execute(
            select(PlanCourse).where(PlanCourse.plan_id == plan.id)
        ).scalars()
    }

    load = [0.0] * terms
    for course_id, term in existing.items():
        if 0 <= term < terms and course_id in info:
            load[term] += info[course_id].credits

    targets = _target_courses(all_courses)
    height = _heights(targets, prereqs)
    remaining = [course for course in targets if course.id not in existing]
    # Courses with an advising-recommended term are seated first so that term is
    # still empty enough to take them. After that, highest critical path first,
    # then by code so a given catalog always produces the same schedule.
    remaining.sort(
        key=lambda course: (
            0 if course.preferred_term is not None else 1,
            -height[course.id],
            course.code,
        )
    )

    placements = dict(existing)
    additions: list[PlanCourse] = []

    # A course can only be placed once its prerequisites are, and sorting by
    # height does not guarantee that on its own: two courses of equal height can
    # depend on each other's neighbours. Sweeping repeatedly until a pass places
    # nothing settles it, and the sort keeps the sweeps in the right order.
    progress = True
    while progress:
        progress = False
        for course in list(remaining):
            earliest = _earliest_legal_term(course, prereqs, placements)
            if earliest is None:
                continue
            term = _choose_term(
                earliest, course.credits, load, terms, course.preferred_term
            )
            if term is None:
                # No term has room. The course stays unplaced and shows up in
                # the "not yet planned" note instead of being forced somewhere.
                remaining.remove(course)
                continue
            placements[course.id] = term
            load[term] += course.credits
            additions.append(
                PlanCourse(plan_id=plan.id, course_id=course.id, term_index=term)
            )
            remaining.remove(course)
            progress = True

    if additions:
        db.add_all(additions)
        db.commit()
