"""Fill the rest of a plan automatically.

Given whatever the student has placed by hand, this lays out the remaining
degree. Existing placements are never moved, so the feature is additive and
pressing it cannot lose work.

There are two halves. Choosing *what* to take, which is now driven by the
program's requirement rows rather than a hardcoded course list, and choosing
*when*, which is a scheduling problem.

**Choosing what.** Each requirement row names its options. Picking the first
alphabetically is a trap: the mechanics requirement lists MEAM 1100 before
PHYS 0150, and MEAM 1100 drags in a lab course that no requirement asks for.
So options are scored by the size of the prerequisite closure they would add
to the plan, and the cheapest wins. PHYS 0150 needs only MATH 1400, which is
already required, so it costs nothing; MEAM 1100 costs one extra course.

**Choosing when.** Two things make the output a schedule a person would follow
rather than merely a legal one.

Ordering is by critical path. Each course gets a height: the length of the
longest chain of courses that depend on it. CIS 1200 is high because CIS 1210,
CIS 3200 and the systems courses sit downstream. An elective slot is zero.
Scheduling by height descending puts the long chains into the early terms. A
plain topological order does not do this: it would hand the first term to four
electives and push CIS 1210 into third year, which is a valid plan and a
useless one.

Placement is balanced rather than earliest-fit. A course goes into the first
term at or after its earliest legal term that is still under a soft target of
roughly one eighth of the degree, and only uses the headroom up to the real
overload limit when no such term exists. Earliest-fit alone packs the first
years to the cap and leaves the last term empty.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import MATCH_EXPLICIT, MATCH_PATTERN, MATCH_SLOT, Course, Plan, PlanCourse
from .audit import DegreeAudit, build_requirement_views
from .planner import equivalence_map
from .plans import load_courses, load_prerequisites


def _closure(course_id, prereqs, have: set[int], memo: dict[int, frozenset[int]]):
    """Courses that would have to join `have` for this one to be takeable.

    Each OR-group contributes whichever option is cheapest to add, which is
    what makes PHYS 0150 win over MEAM 1100 for the mechanics requirement.
    """
    if course_id in have:
        return frozenset()
    if course_id in memo:
        return memo[course_id]
    memo[course_id] = frozenset({course_id})  # guards cyclic corequisites

    needed = {course_id}
    for group in prereqs.get(course_id, []):
        if any(rid in have for rid in group.required_ids):
            continue
        best = min(
            (_closure(rid, prereqs, have, memo) for rid in group.required_ids),
            key=len,
            default=frozenset(),
        )
        needed |= best
    result = frozenset(needed)
    memo[course_id] = result
    return result


def choose_courses(db: Session, plan: Plan, already: set[int]) -> list[Course]:
    """Which courses to add, driven entirely by the program's requirements.

    The loop below asks the audit what is still unsatisfied, adds one course
    toward each outstanding row, and re-runs the matching. Guessing instead is
    what an earlier version did, and it was wrong in both directions: it either
    added a second chemistry sequence because a prerequisite had already
    supplied the first, or skipped a row entirely because a course that looked
    like it could fill it was in fact already spent on another requirement.
    Only the matcher knows which, so only the matcher is asked.
    """
    all_courses = {c.id: c for c in db.execute(select(Course)).scalars().all()}
    prereqs = load_prerequisites(db)
    info = load_courses(db)
    requirements = build_requirement_views(plan.program)
    engine = DegreeAudit(requirements, info, equivalence_map(info))

    by_tag: dict[str, list[Course]] = defaultdict(list)
    for course in all_courses.values():
        if course.is_slot and course.slot_tag:
            by_tag[course.slot_tag].append(course)
    for courses in by_tag.values():
        courses.sort(key=lambda c: c.code)

    chosen: list[int] = []
    have = set(already)
    claimed_keys = {
        all_courses[cid].equivalence_key
        for cid in already
        if cid in all_courses and all_courses[cid].equivalence_key
    }

    def take(course: Course) -> bool:
        if course.id in have:
            return False
        if course.equivalence_key and course.equivalence_key in claimed_keys:
            return False
        if course.equivalence_key:
            claimed_keys.add(course.equivalence_key)
        have.add(course.id)
        chosen.append(course.id)
        return True

    def candidates(requirement) -> list[Course]:
        if requirement.match_kind == MATCH_SLOT:
            pool = [c for c in by_tag.get(requirement.slot_tag or "", []) if c.id not in have]
        elif requirement.match_kind == MATCH_PATTERN:
            pool = [
                c for c in all_courses.values()
                if not c.is_slot
                and c.subject in requirement.subjects
                and c.level is not None
                and c.level >= (requirement.min_level or 0)
                and c.id not in have
            ]
        else:
            pool = [
                all_courses[cid] for cid in requirement.option_ids
                if cid in all_courses and cid not in have
            ]
        # Cheapest to reach first: PHYS 0150 needs only MATH 1400, which the
        # degree already requires, while MEAM 1100 drags in a lab course too.
        return sorted(pool, key=lambda c: (len(_closure(c.id, prereqs, have, {})), c.code))

    # Bounded by the number of requirement slots, since every pass that does
    # not add a course exits.
    for _ in range(sum(r.slots for r in requirements) + 1):
        result = engine.run(sorted(have))
        outstanding = [row for row in result.requirements if not row.satisfied]
        if not outstanding:
            break

        progress = False
        for row in outstanding:
            for course in candidates(row.requirement):
                support = sorted(
                    _closure(course.id, prereqs, have, {}) - {course.id},
                    key=lambda cid: all_courses[cid].code,
                )
                if take(course):
                    for support_id in support:
                        take(all_courses[support_id])
                    progress = True
                    break
        if not progress:
            break

    return [all_courses[cid] for cid in chosen]


def _heights(course_ids: list[int], prereqs) -> dict[int, int]:
    """Longest chain of dependents below each course, by memoized descent."""
    target = set(course_ids)
    dependents: dict[int, set[int]] = defaultdict(set)
    for course_id in course_ids:
        for group in prereqs.get(course_id, []):
            for required_id in group.required_ids:
                if required_id in target:
                    dependents[required_id].add(course_id)

    height: dict[int, int] = {}
    visiting: set[int] = set()

    def compute(course_id: int) -> int:
        if course_id in height:
            return height[course_id]
        if course_id in visiting:
            return 0
        visiting.add(course_id)
        below = [compute(child) for child in dependents.get(course_id, ())]
        visiting.discard(course_id)
        height[course_id] = 1 + max(below) if below else 0
        return height[course_id]

    for course_id in course_ids:
        compute(course_id)
    return height


def _earliest_legal_term(course, prereqs, placements: dict[int, int]) -> int | None:
    earliest = course.min_term_index
    for group in prereqs.get(course.id, []):
        scheduled = [placements[rid] for rid in group.required_ids if rid in placements]
        if not scheduled:
            return None
        first = min(scheduled)
        earliest = max(earliest, first if group.allow_concurrent else first + 1)
    return earliest


def _choose_term(earliest, credits, load, terms, preferred=None) -> int | None:
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


def autofill_plan(db: Session, plan: Plan) -> None:
    terms = plan.program.term_count
    info = load_courses(db)
    prereqs = load_prerequisites(db)

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

    targets = choose_courses(db, plan, set(existing))
    if not targets:
        return

    # Spread the soft cap over however many terms this program spans, so a
    # twelve-unit second major does not try to fill four years.
    total = sum(course.credits for course in targets) + sum(load)
    soft = max(settings.balanced_term_credits, 0.0)
    settings_soft = min(soft, max(1.0, total / terms + 0.25))

    height = _heights([c.id for c in targets], prereqs)
    remaining = sorted(
        targets,
        key=lambda course: (
            0 if course.preferred_term is not None else 1,
            -height[course.id],
            course.code,
        ),
    )

    placements = dict(existing)
    additions: list[PlanCourse] = []

    # Sorting by height does not guarantee prerequisites are placed first, since
    # two courses of equal height can depend on each other's neighbours.
    # Sweeping until a pass places nothing settles it.
    progress = True
    while progress:
        progress = False
        for course in list(remaining):
            earliest = _earliest_legal_term(course, prereqs, placements)
            if earliest is None:
                continue
            term = _pick(earliest, course, load, terms, settings_soft)
            if term is None:
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


def _pick(earliest, course, load, terms, soft) -> int | None:
    if (
        course.preferred_term is not None
        and earliest <= course.preferred_term < terms
        and load[course.preferred_term] + course.credits <= settings.max_term_credits
    ):
        return course.preferred_term
    for cap in (soft, settings.max_term_credits):
        for term in range(earliest, terms):
            if load[term] + course.credits <= cap:
                return term
    return None
