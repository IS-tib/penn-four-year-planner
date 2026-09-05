"""Plan validation and degree audit.

All of this runs on the server. The browser never decides whether a plan is
valid, it only renders what the API says, which means the client and the server
cannot drift apart and a hand-rolled request cannot slip past the rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..catalog import (
    CATEGORY_ORDER,
    CATEGORY_TARGETS,
    CIS_ELECTIVE_LEVEL_CAP,
    CORE,
    PUBLISHED_DEGREE_TOTAL_CU,
    TRACKED_TOTAL_CU,
)
from ..config import settings

ERROR = "error"
WARNING = "warning"
INFO = "info"


def equivalence_map(courses: dict[int, "CourseInfo"]) -> dict[int, set[int]]:
    """course id to the ids of every other course cross-listed with it."""
    by_key: dict[str, set[int]] = {}
    for course in courses.values():
        if course.equivalence_key:
            by_key.setdefault(course.equivalence_key, set()).add(course.id)
    return {
        course.id: by_key[course.equivalence_key] - {course.id}
        for course in courses.values()
        if course.equivalence_key
    }


def canonical_courses(courses: dict[int, "CourseInfo"]) -> list["CourseInfo"]:
    """One representative per course, collapsing cross-listed numbers.

    The undergraduate number wins, because it sorts first and because it is the
    one the degree requirements are written against.
    """
    chosen: dict[str, CourseInfo] = {}
    singles: list[CourseInfo] = []
    for course in courses.values():
        if not course.equivalence_key:
            singles.append(course)
            continue
        current = chosen.get(course.equivalence_key)
        if current is None or course.code < current.code:
            chosen[course.equivalence_key] = course
    return sorted([*singles, *chosen.values()], key=lambda course: course.code)


def term_label(start_year: int, term_index: int) -> str:
    """Term 0 is the fall of the starting year, then alternating spring/fall."""
    season = "Fall" if term_index % 2 == 0 else "Spring"
    year = start_year + (term_index + 1) // 2
    return f"{season} {year}"


@dataclass(frozen=True)
class PrereqGroup:
    """One OR-group. Satisfied when any member course is scheduled early enough."""

    required_ids: tuple[int, ...]
    allow_concurrent: bool


@dataclass(frozen=True)
class CourseInfo:
    id: int
    code: str
    title: str
    credits: float
    category: str
    min_term_index: int = 0
    level: int | None = None
    equivalence_key: str | None = None


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    course_code: str | None = None
    term_index: int | None = None


@dataclass(frozen=True)
class CategoryProgress:
    category: str
    planned: float
    target: float


class PlanValidator:
    """Checks one plan's placements against prerequisite and load rules."""

    def __init__(
        self,
        courses: dict[int, CourseInfo],
        prereqs: dict[int, list[PrereqGroup]],
        start_year: int,
    ) -> None:
        self._courses = courses
        self._prereqs = prereqs
        self._start_year = start_year
        self._equivalents = equivalence_map(courses)

    def validate(self, placements: dict[int, int]) -> list[Diagnostic]:
        """placements maps course id to term index."""
        found: list[Diagnostic] = []
        found.extend(self._prerequisite_diagnostics(placements))
        found.extend(self._standing_diagnostics(placements))
        found.extend(self._duplicate_diagnostics(placements))
        found.extend(self._term_load_diagnostics(placements))
        found.extend(self._elective_level_diagnostics(placements))
        found.extend(self._core_coverage_diagnostics(placements))
        return found

    def _satisfying_ids(self, required_ids: tuple[int, ...]) -> set[int]:
        """Every course id that would satisfy a requirement for one of these.

        A prerequisite naming CIS 4500 is equally satisfied by CIS 5500, since
        they are one cross-listed course. Expanding here means the rest of the
        validator never has to think about it.
        """
        satisfying: set[int] = set()
        for course_id in required_ids:
            satisfying.add(course_id)
            satisfying |= self._equivalents.get(course_id, set())
        return satisfying

    # -- duplicates -------------------------------------------------------
    def _duplicate_diagnostics(self, placements: dict[int, int]) -> list[Diagnostic]:
        by_key: dict[str, list[int]] = {}
        for course_id in placements:
            course = self._courses.get(course_id)
            if course is None or not course.equivalence_key:
                continue
            by_key.setdefault(course.equivalence_key, []).append(course_id)

        out: list[Diagnostic] = []
        for course_ids in by_key.values():
            if len(course_ids) < 2:
                continue
            codes = sorted(self._courses[cid].code for cid in course_ids)
            latest = max(course_ids, key=lambda cid: (placements[cid], self._courses[cid].code))
            out.append(
                Diagnostic(
                    severity=ERROR,
                    code="duplicate_course",
                    message=(
                        f"{' and '.join(codes)} are the same course cross-listed at two "
                        "numbers, so only one of them can count. Remove one."
                    ),
                    course_code=self._courses[latest].code,
                    term_index=placements[latest],
                )
            )
        return out

    # -- elective composition ---------------------------------------------
    def _elective_level_diagnostics(self, placements: dict[int, int]) -> list[Diagnostic]:
        rule = CIS_ELECTIVE_LEVEL_CAP
        counted = [
            course
            for course in (self._courses.get(cid) for cid in placements)
            if course is not None
            and course.category == rule["category"]
            and course.level == rule["level"]
        ]
        total = round(sum(course.credits for course in counted), 2)
        if total <= rule["max_credits"]:
            return []
        codes = ", ".join(sorted(course.code for course in counted))
        return [
            Diagnostic(
                severity=ERROR,
                code="elective_level_cap",
                message=(
                    f"The CIS elective requirement allows at most "
                    f"{_cu(rule['max_credits'])} from {rule['level']}-level courses, and "
                    f"this plan has {_cu(total)} of them: {codes}."
                ),
            )
        ]

    # -- class standing ---------------------------------------------------
    def _standing_diagnostics(self, placements: dict[int, int]) -> list[Diagnostic]:
        out: list[Diagnostic] = []
        for course_id, term in sorted(placements.items(), key=lambda kv: (kv[1], kv[0])):
            course = self._courses.get(course_id)
            if course is None or term >= course.min_term_index:
                continue
            out.append(
                Diagnostic(
                    severity=ERROR,
                    code="standing_requirement",
                    message=(
                        f"{course.code} cannot be taken before "
                        f"{term_label(self._start_year, course.min_term_index)}, "
                        "because the catalog requires senior standing."
                    ),
                    course_code=course.code,
                    term_index=term,
                )
            )
        return out

    # -- prerequisites ----------------------------------------------------
    def _prerequisite_diagnostics(self, placements: dict[int, int]) -> list[Diagnostic]:
        out: list[Diagnostic] = []
        for course_id, term in sorted(placements.items(), key=lambda kv: (kv[1], kv[0])):
            course = self._courses.get(course_id)
            if course is None:
                continue
            for group in self._prereqs.get(course_id, []):
                latest_allowed = term if group.allow_concurrent else term - 1
                scheduled = [
                    (rid, placements[rid])
                    for rid in self._satisfying_ids(group.required_ids)
                    if rid in placements
                ]
                if any(placed_term <= latest_allowed for _, placed_term in scheduled):
                    continue

                names = self._describe(group.required_ids)
                if not scheduled:
                    out.append(
                        Diagnostic(
                            severity=ERROR,
                            code="missing_prerequisite",
                            message=(
                                f"{course.code} requires {names}, which is not in this plan."
                            ),
                            course_code=course.code,
                            term_index=term,
                        )
                    )
                    continue

                # Everything that could satisfy the group is scheduled, just not
                # early enough. Name the earliest one, since that is the term the
                # student would have to move.
                earliest_id, earliest_term = min(scheduled, key=lambda pair: pair[1])
                earliest = self._courses[earliest_id]
                when = "at the same time as or before" if group.allow_concurrent else "before"
                out.append(
                    Diagnostic(
                        severity=ERROR,
                        code="prerequisite_out_of_order",
                        message=(
                            f"{course.code} is in {term_label(self._start_year, term)} but "
                            f"{earliest.code} is not until "
                            f"{term_label(self._start_year, earliest_term)}. "
                            f"{names} must come {when} it."
                        ),
                        course_code=course.code,
                        term_index=term,
                    )
                )
        return out

    def _describe(self, ids: tuple[int, ...]) -> str:
        codes = [self._courses[i].code for i in ids if i in self._courses]
        if not codes:
            return "a course not in the catalog"
        if len(codes) == 1:
            return codes[0]
        return " or ".join([", ".join(codes[:-1]), codes[-1]])

    # -- term load --------------------------------------------------------
    def _term_load_diagnostics(self, placements: dict[int, int]) -> list[Diagnostic]:
        out: list[Diagnostic] = []
        for term in range(settings.terms_per_plan):
            credits = sum(
                self._courses[cid].credits
                for cid, t in placements.items()
                if t == term and cid in self._courses
            )
            if credits == 0:
                continue
            label = term_label(self._start_year, term)
            if credits > settings.max_term_credits:
                out.append(
                    Diagnostic(
                        severity=WARNING,
                        code="term_overload",
                        message=(
                            f"{label} is {_cu(credits)}. Anything above "
                            f"{_cu(settings.max_term_credits)} needs an overload petition."
                        ),
                        term_index=term,
                    )
                )
            elif credits < settings.min_term_credits:
                out.append(
                    Diagnostic(
                        severity=WARNING,
                        code="term_underload",
                        message=(
                            f"{label} is {_cu(credits)}, below the "
                            f"{_cu(settings.min_term_credits)} full-time minimum."
                        ),
                        term_index=term,
                    )
                )
        return out

    # -- core coverage ----------------------------------------------------
    def _core_coverage_diagnostics(self, placements: dict[int, int]) -> list[Diagnostic]:
        def covered(course: CourseInfo) -> bool:
            if course.id in placements:
                return True
            # CIS 5480 satisfies the operating systems core requirement just as
            # CIS 4480 does, so a plan holding either has covered it.
            return any(twin in placements for twin in self._equivalents.get(course.id, ()))

        missing = sorted(
            course.code
            for course in canonical_courses(self._courses)
            if course.category == CORE and not covered(course)
        )
        if not missing:
            return []
        listed = ", ".join(missing)
        noun = "course is" if len(missing) == 1 else "courses are"
        return [
            Diagnostic(
                severity=INFO,
                code="core_not_yet_planned",
                message=f"{len(missing)} required CIS core {noun} not in this plan: {listed}.",
            )
        ]


class DegreeAudit:
    """Sums planned course units per requirement bucket."""

    def __init__(self, courses: dict[int, CourseInfo]) -> None:
        self._courses = courses

    def progress(self, placements: dict[int, int]) -> list[CategoryProgress]:
        planned: dict[str, float] = {category: 0.0 for category in CATEGORY_ORDER}
        for course_id in placements:
            course = self._courses.get(course_id)
            if course is None:
                continue
            planned[course.category] = planned.get(course.category, 0.0) + course.credits
        return [
            CategoryProgress(
                category=category,
                planned=round(planned.get(category, 0.0), 2),
                target=CATEGORY_TARGETS[category],
            )
            for category in CATEGORY_ORDER
        ]

    def total_planned(self, placements: dict[int, int]) -> float:
        total = sum(
            self._courses[cid].credits for cid in placements if cid in self._courses
        )
        return round(total, 2)

    @property
    def degree_total(self) -> float:
        """Course units this app tracks, which is the sum of its buckets."""
        return TRACKED_TOTAL_CU

    @property
    def published_degree_total(self) -> float:
        """Course units Penn publishes for the degree."""
        return PUBLISHED_DEGREE_TOTAL_CU


def _cu(value: float) -> str:
    formatted = f"{value:g}"
    return f"{formatted} CU"
