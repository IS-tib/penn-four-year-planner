"""What could a student actually take in a given term?

This is the question the validator answers backwards. The validator takes a
placement and reports what is wrong with it; this walks the same rules forward
and reports every course that would be fine. Both read the same prerequisite
graph, so they cannot disagree: a course this returns for a term is a course the
validator will accept in that term.

The ordering matters more than it looks. A student opening this list wants to
see the courses that keep the degree moving, not an alphabetical dump, so
results are sorted by how much they unlock and then by requirement bucket.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..catalog import CATEGORY_ORDER
from ..config import settings
from .planner import CourseInfo, PrereqGroup, equivalence_map


@dataclass(frozen=True)
class EligibleCourse:
    course_id: int
    code: str
    title: str
    credits: float
    category: str
    is_placeholder: bool
    # How many other courses this one is a prerequisite for, directly or not.
    unlocks: int
    # True when adding it would push the term past the overload threshold. It
    # is still offered, because a student may well intend to petition, but it
    # is offered with a warning rather than silently.
    would_overload: bool


class EligibilityFinder:
    def __init__(
        self,
        courses: dict[int, CourseInfo],
        prereqs: dict[int, list[PrereqGroup]],
        placeholders: set[int],
    ) -> None:
        self._courses = courses
        self._prereqs = prereqs
        self._placeholders = placeholders
        self._equivalents = equivalence_map(courses)
        self._reach = _transitive_dependents(courses, prereqs)

    def _satisfying_ids(self, required_ids: tuple[int, ...]) -> set[int]:
        satisfying: set[int] = set()
        for course_id in required_ids:
            satisfying.add(course_id)
            satisfying |= self._equivalents.get(course_id, set())
        return satisfying

    def _prerequisites_met(self, course_id: int, term: int, placements: dict[int, int]) -> bool:
        for group in self._prereqs.get(course_id, []):
            latest_allowed = term if group.allow_concurrent else term - 1
            met = any(
                placements[rid] <= latest_allowed
                for rid in self._satisfying_ids(group.required_ids)
                if rid in placements
            )
            if not met:
                return False
        return True

    def _already_covered(self, course_id: int, placements: dict[int, int]) -> bool:
        if course_id in placements:
            return True
        return any(twin in placements for twin in self._equivalents.get(course_id, ()))

    def find(
        self,
        placements: dict[int, int],
        term: int,
        *,
        category: str | None = None,
        exclude_placeholders: bool = False,
    ) -> list[EligibleCourse]:
        term_load = round(
            sum(
                self._courses[cid].credits
                for cid, placed in placements.items()
                if placed == term and cid in self._courses
            ),
            2,
        )

        results: list[EligibleCourse] = []
        for course in self._courses.values():
            if category is not None and course.category != category:
                continue
            if exclude_placeholders and course.id in self._placeholders:
                continue
            if self._already_covered(course.id, placements):
                continue
            if term < course.min_term_index:
                continue
            if not self._prerequisites_met(course.id, term, placements):
                continue

            results.append(
                EligibleCourse(
                    course_id=course.id,
                    code=course.code,
                    title=course.title,
                    credits=course.credits,
                    category=course.category,
                    is_placeholder=course.id in self._placeholders,
                    unlocks=len(self._reach.get(course.id, ())),
                    would_overload=(
                        term_load + course.credits > settings.max_term_credits
                    ),
                )
            )

        order = {name: index for index, name in enumerate(CATEGORY_ORDER)}
        results.sort(
            key=lambda item: (
                item.would_overload,          # things that fit come first
                -item.unlocks,                # then whatever opens the most doors
                order.get(item.category, 99),
                item.code,
            )
        )
        return results


def _transitive_dependents(
    courses: dict[int, CourseInfo], prereqs: dict[int, list[PrereqGroup]]
) -> dict[int, set[int]]:
    """Everything downstream of each course, not just its direct dependents.

    CIS 1200 directly unlocks CIS 1210 and CIS 2400, but transitively it also
    unlocks CIS 3200, CIS 4480 and CIS 4710. The transitive count is the honest
    measure of how much a course matters to the rest of the degree, and it is
    what the ordering above uses.
    """
    direct: dict[int, set[int]] = {}
    for course_id, groups in prereqs.items():
        for group in groups:
            for required_id in group.required_ids:
                direct.setdefault(required_id, set()).add(course_id)

    reach: dict[int, set[int]] = {}
    visiting: set[int] = set()

    def walk(course_id: int) -> set[int]:
        if course_id in reach:
            return reach[course_id]
        if course_id in visiting:
            return set()
        visiting.add(course_id)
        found: set[int] = set()
        for child in direct.get(course_id, ()):
            found.add(child)
            found |= walk(child)
        visiting.discard(course_id)
        reach[course_id] = found
        return found

    for course_id in courses:
        walk(course_id)
    return reach
