"""What happens if you switch majors.

This is the question a degree planner can answer and a semester scheduler
cannot, and it is the reason the requirement model is data rather than code.
Given a plan built under one program, it re-runs the audit under a different
program and reports three things a student actually wants to know: which
courses still count, which become dead weight, and roughly how far behind they
would be.

The first two fall straight out of the matching. Re-running the audit against
the target program's requirements assigns each planned course to a requirement
or leaves it unassigned, and unassigned is exactly what "wasted" means.

The third is a bound, not a prediction, and it is reported as one. Two things
independently limit how fast a student can finish, and the answer is whichever
binds harder:

**Capacity.** Whatever room is left under the course-load cap across the terms
the plan already spans. If the outstanding requirements need more course units
than that, the overflow has to go somewhere, and each extra term holds at most
the overload threshold.

**Chain length.** Prerequisites are a DAG, and a chain of five courses takes at
least five terms no matter how light the load. The longest chain among the
outstanding requirements is a floor that no amount of spare capacity lowers.

Neither is a promise, because course offerings, term availability and advisor
approval are all outside what the catalog prints. The number is honest about
being a lower bound.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..config import settings
from .audit import AuditResult, CourseView, DegreeAudit, RequirementView
from .planner import PrereqGroup


@dataclass
class SwitchAnalysis:
    carried_over: list[int] = field(default_factory=list)
    wasted: list[int] = field(default_factory=list)
    carried_credits: float = 0.0
    wasted_credits: float = 0.0
    remaining_credits: float = 0.0
    outstanding: int = 0
    free_capacity: float = 0.0
    extra_terms_from_load: int = 0
    longest_remaining_chain: int = 0
    extra_terms_from_chain: int = 0
    min_extra_terms: int = 0
    audit: AuditResult | None = None


def _chain_depth(
    course_id: int,
    prereqs: dict[int, list[PrereqGroup]],
    already: set[int],
    memo: dict[int, int],
    stack: set[int],
) -> int:
    """Terms of prerequisite chain still needed above a course.

    Anything already in the plan counts as done, so a chain only measures what
    is genuinely still ahead. The stack guard keeps a cyclic corequisite pair in
    the seed data from recursing forever.
    """
    if course_id in already:
        return 0
    if course_id in memo:
        return memo[course_id]
    if course_id in stack:
        return 1
    stack.add(course_id)

    depth = 1
    for group in prereqs.get(course_id, []):
        # An OR-group costs whichever of its options is cheapest to reach.
        best = min(
            (_chain_depth(rid, prereqs, already, memo, stack) for rid in group.required_ids),
            default=0,
        )
        depth = max(depth, best + 1)

    stack.discard(course_id)
    memo[course_id] = depth
    return depth


def analyse_switch(
    requirements: list[RequirementView],
    courses: dict[int, CourseView],
    prereqs: dict[int, list[PrereqGroup]],
    equivalents: dict[int, set[int]],
    placements: dict[int, int],
    designations: dict[int, str],
    term_count: int,
) -> SwitchAnalysis:
    audit = DegreeAudit(requirements, courses, equivalents)
    result = audit.run(list(placements), designations)

    matched = {cid for row in result.requirements for cid in row.matched}
    wasted = [cid for cid in placements if cid in courses and cid not in matched]

    carried_credits = round(sum(courses[cid].credits for cid in matched), 2)
    wasted_credits = round(sum(courses[cid].credits for cid in wasted), 2)

    outstanding = [row for row in result.requirements if not row.satisfied]
    remaining_credits = round(
        sum(
            row.requirement.credits
            * (row.requirement.slots - row.filled_slots)
            / row.requirement.slots
            for row in outstanding
        ),
        2,
    )

    # How much room is left under the load cap in the terms the plan spans.
    load = [0.0] * term_count
    for course_id, term in placements.items():
        if course_id in matched and 0 <= term < term_count:
            load[term] += courses[course_id].credits
    free_capacity = round(
        sum(max(0.0, settings.max_term_credits - used) for used in load), 2
    )

    overflow = max(0.0, remaining_credits - free_capacity)
    extra_from_load = math.ceil(overflow / settings.max_term_credits) if overflow else 0

    # The longest prerequisite chain still ahead, over the named courses the
    # outstanding requirements would accept. Open slots have no prerequisites,
    # so they cannot lengthen a chain.
    memo: dict[int, int] = {}
    longest = 0
    for row in outstanding:
        options = row.requirement.option_ids
        if not options:
            continue
        cheapest = min(
            _chain_depth(cid, prereqs, set(placements), memo, set()) for cid in options
        )
        longest = max(longest, cheapest)

    terms_used = max((term for term in placements.values()), default=-1) + 1
    terms_left = max(0, term_count - terms_used)
    extra_from_chain = max(0, longest - terms_left)

    return SwitchAnalysis(
        carried_over=sorted(matched, key=lambda cid: courses[cid].code),
        wasted=sorted(wasted, key=lambda cid: courses[cid].code),
        carried_credits=carried_credits,
        wasted_credits=wasted_credits,
        remaining_credits=remaining_credits,
        outstanding=len(outstanding),
        free_capacity=free_capacity,
        extra_terms_from_load=extra_from_load,
        longest_remaining_chain=longest,
        extra_terms_from_chain=extra_from_chain,
        min_extra_terms=max(extra_from_load, extra_from_chain),
        audit=result,
    )


def verdict(analysis: SwitchAnalysis) -> str:
    """One plain sentence, because the numbers alone do not land."""
    if analysis.min_extra_terms == 0 and analysis.outstanding == 0:
        return "Everything this degree needs is already in the plan."
    if analysis.min_extra_terms == 0:
        return (
            f"This fits in the terms you already have. "
            f"{_cu(analysis.carried_credits)} of your plan carries over and "
            f"{_cu(analysis.remaining_credits)} of requirements are still open."
        )
    semesters = "semester" if analysis.min_extra_terms == 1 else "semesters"
    reason = (
        "because of the course load"
        if analysis.extra_terms_from_load >= analysis.extra_terms_from_chain
        else "because of how long the prerequisite chains are"
    )
    return (
        f"At least {analysis.min_extra_terms} extra {semesters}, {reason}. "
        f"{_cu(analysis.carried_credits)} carries over and "
        f"{_cu(analysis.wasted_credits)} would no longer count."
    )


def _cu(value: float) -> str:
    return f"{value:g} CU"
