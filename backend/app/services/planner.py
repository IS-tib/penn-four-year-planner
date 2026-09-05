"""Plan validation: ordering, class standing, duplicates and course load.

All of this runs on the server. The browser never decides whether a plan is
valid, it only renders what the API says, which means the client and the server
cannot drift apart and a hand-rolled request cannot slip past the rules.

Degree completeness is a separate question answered by `audit.py`, because it
is a different kind of problem: this module asks whether a plan can be executed
in the order given, and the audit asks whether executing it earns the degree.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import settings

ERROR = "error"
WARNING = "warning"
INFO = "info"

# The CIS elective requirement caps 1000-level work, per the footnote printed
# on both the Computer Science and Digital Media Design program pages.
CIS_ELECTIVE_TAG = "cis-el"
CIS_ELECTIVE_LEVEL_CAP = 1.0


def term_label(start_year: int, term_index: int) -> str:
    """Term 0 is the fall of the starting year, then alternating spring/fall."""
    season = "Fall" if term_index % 2 == 0 else "Spring"
    year = start_year + (term_index + 1) // 2
    return f"{season} {year}"


def year_of(term_index: int) -> int:
    return term_index // 2 + 1


STANDING = {1: "first year", 2: "sophomore", 3: "junior", 4: "senior"}


def standing_name(term_index: int) -> str:
    return STANDING.get(year_of(term_index), f"year {year_of(term_index)}")


@dataclass(frozen=True)
class PrereqGroup:
    """One OR-group. Satisfied when any member is scheduled early enough."""

    required_ids: tuple[int, ...]
    allow_concurrent: bool


@dataclass(frozen=True)
class CourseInfo:
    id: int
    code: str
    title: str
    credits: float
    subject: str
    level: int | None = None
    is_slot: bool = False
    slot_tag: str | None = None
    min_term_index: int = 0
    equivalence_key: str | None = None


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    course_code: str | None = None
    term_index: int | None = None


def equivalence_map(courses: dict[int, CourseInfo]) -> dict[int, set[int]]:
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


class PlanValidator:
    """Checks one plan's placements against ordering and load rules."""

    def __init__(
        self,
        courses: dict[int, CourseInfo],
        prereqs: dict[int, list[PrereqGroup]],
        start_year: int,
        term_count: int = 8,
        check_term_load: bool = True,
    ) -> None:
        self._courses = courses
        self._prereqs = prereqs
        self._start_year = start_year
        self._term_count = term_count
        self._check_term_load = check_term_load
        self._equivalents = equivalence_map(courses)

    def validate(
        self,
        placements: dict[int, int],
        designations: dict[int, str] | None = None,
    ) -> list[Diagnostic]:
        """placements maps course id to term index."""
        found: list[Diagnostic] = []
        found.extend(self._prerequisite_diagnostics(placements))
        found.extend(self._standing_diagnostics(placements))
        found.extend(self._duplicate_diagnostics(placements))
        found.extend(self._term_load_diagnostics(placements))
        found.extend(self._elective_level_diagnostics(placements, designations or {}))
        return found

    def _satisfying_ids(self, required_ids: tuple[int, ...]) -> set[int]:
        """Every course id that would satisfy a requirement for one of these.

        A prerequisite naming CIS 4500 is equally satisfied by CIS 5500, since
        they are one cross-listed course.
        """
        satisfying: set[int] = set()
        for course_id in required_ids:
            satisfying.add(course_id)
            satisfying |= self._equivalents.get(course_id, set())
        return satisfying

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
                if any(placed <= latest_allowed for _, placed in scheduled):
                    continue

                names = self._describe(group.required_ids)
                if not scheduled:
                    out.append(
                        Diagnostic(
                            severity=ERROR,
                            code="missing_prerequisite",
                            message=f"{course.code} requires {names}, which is not in this plan.",
                            course_code=course.code,
                            term_index=term,
                        )
                    )
                    continue

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
                        f"{term_label(self._start_year, course.min_term_index)}, because "
                        f"the catalog requires {standing_name(course.min_term_index)} standing."
                    ),
                    course_code=course.code,
                    term_index=term,
                )
            )
        return out

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

    # -- term load --------------------------------------------------------
    def _term_load_diagnostics(self, placements: dict[int, int]) -> list[Diagnostic]:
        if not self._check_term_load:
            return []
        out: list[Diagnostic] = []
        for term in range(self._term_count):
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

    # -- elective composition ---------------------------------------------
    def _elective_level_diagnostics(
        self, placements: dict[int, int], designations: dict[int, str]
    ) -> list[Diagnostic]:
        counted = [
            course
            for course in (self._courses.get(cid) for cid in placements)
            if course is not None
            and course.level == 1000
            and designations.get(course.id) == CIS_ELECTIVE_TAG
        ]
        total = round(sum(course.credits for course in counted), 2)
        if total <= CIS_ELECTIVE_LEVEL_CAP:
            return []
        codes = ", ".join(sorted(course.code for course in counted))
        return [
            Diagnostic(
                severity=ERROR,
                code="elective_level_cap",
                message=(
                    f"The CIS elective requirement allows at most "
                    f"{_cu(CIS_ELECTIVE_LEVEL_CAP)} from 1000-level courses, and this "
                    f"plan uses {_cu(total)} of them: {codes}."
                ),
            )
        ]


def coverage_diagnostic(audit_result, start_year: int) -> list[Diagnostic]:
    """One informational line naming what the degree still needs.

    Derived from the audit rather than from a hardcoded course list, which is
    what lets it work for a degree this module has never heard of.
    """
    outstanding = [r for r in audit_result.requirements if not r.satisfied]
    if not outstanding:
        return [
            Diagnostic(
                severity=INFO,
                code="degree_complete",
                message="Every requirement for this degree is filled.",
            )
        ]
    named = [
        r.requirement.label
        for r in outstanding
        if r.requirement.match_kind == "explicit" and r.requirement.slots == 1
    ][:6]
    tail = f" Including {', '.join(named)}." if named else ""
    noun = "requirement is" if len(outstanding) == 1 else "requirements are"
    return [
        Diagnostic(
            severity=INFO,
            code="requirements_outstanding",
            message=f"{len(outstanding)} {noun} not yet filled.{tail}",
        )
    ]


def _cu(value: float) -> str:
    return f"{value:g} CU"
