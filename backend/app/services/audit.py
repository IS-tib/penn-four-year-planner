"""Deciding which requirements a plan actually satisfies.

The obvious way to audit a degree is to add up course units per category. It is
also wrong, and Penn says so in its own footnote on the Mathematics BA page:

    "You may count no more than one course toward both a Major and a Sector
    requirement."

That is not a counting rule, it is a constraint: each course may be spent once.
So the question "does this plan satisfy this degree" is a **maximum bipartite
matching** between planned courses and requirement slots. Courses sit on one
side with capacity one. Requirements sit on the other with capacity equal to
however many courses the row consumes, which is one for most rows and four for
something like "Select 4 Social Science or Humanities courses". An edge exists
where a course is allowed to fill a requirement.

Why the distinction is not academic: CHEM 1012 can satisfy Bioengineering's
chemistry row and also appears in Biology's physical-sciences list. MATH 1400
appears in nearly every program. Summing credits would let one course pay for
two requirements and report a plan complete when it is not. Matching cannot,
because the algorithm hands each course to exactly one requirement or leaves it
unassigned.

The algorithm is Kuhn's, augmenting paths, extended so the right-hand side has
capacity rather than being one-to-one. Worst case is O(V*E), and the graphs
here are a few hundred edges, so it runs in well under a millisecond.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import MATCH_EXPLICIT, MATCH_PATTERN, MATCH_SLOT
from .planner import CourseInfo

# The matcher and the validator want exactly the same view of a course, so they
# share one. Two near-identical dataclasses would only drift.
CourseView = CourseInfo


@dataclass(frozen=True)
class RequirementView:
    id: int
    group_position: int
    group_name: str
    group_notes: str
    position: int
    label: str
    credits: float
    slots: int
    match_kind: str
    option_ids: frozenset[int]
    subjects: tuple[str, ...]
    min_level: int | None
    slot_tag: str | None
    notes: str


@dataclass
class RequirementResult:
    requirement: RequirementView
    matched: list[int] = field(default_factory=list)

    @property
    def satisfied(self) -> bool:
        return len(self.matched) >= self.requirement.slots

    @property
    def filled_slots(self) -> int:
        return len(self.matched)


@dataclass
class AuditResult:
    requirements: list[RequirementResult]
    # Planned courses that are not counting toward anything in this program.
    unassigned: list[int]
    credits_required: float
    credits_matched: float
    credits_planned: float

    @property
    def complete(self) -> bool:
        return all(result.satisfied for result in self.requirements)

    @property
    def satisfied_count(self) -> int:
        return sum(1 for result in self.requirements if result.satisfied)


class DegreeAudit:
    """Matches a set of planned courses against one program's requirements."""

    def __init__(
        self,
        requirements: list[RequirementView],
        courses: dict[int, CourseView],
        equivalents: dict[int, set[int]] | None = None,
    ) -> None:
        self._requirements = requirements
        self._courses = courses
        self._equivalents = equivalents or {}
        # A requirement naming CIS 4500 is equally met by CIS 5500, so the
        # option set is widened once here rather than checked on every edge.
        self._options = {r.id: self._expand_options(r) for r in requirements}

    # -- the graph ---------------------------------------------------------
    def _accepts(
        self, requirement: RequirementView, course: CourseView, designation: str | None
    ) -> bool:
        if requirement.match_kind == MATCH_SLOT:
            if course.is_slot:
                return course.slot_tag == requirement.slot_tag
            # A real course fills an open row only when the student put it
            # there. The catalog never prints which courses count as humanities,
            # so the app records the student's choice instead of inventing one.
            return designation == requirement.slot_tag
        if course.is_slot:
            # A placeholder never satisfies a named requirement. Letting it
            # would report a degree complete on the strength of an empty box.
            return False
        if requirement.match_kind == MATCH_EXPLICIT:
            return course.id in self._options[requirement.id]
        if requirement.match_kind == MATCH_PATTERN:
            if course.subject not in requirement.subjects:
                return False
            return course.level is not None and course.level >= (requirement.min_level or 0)
        return False

    def _expand_options(self, requirement: RequirementView) -> frozenset[int]:
        expanded = set(requirement.option_ids)
        for course_id in requirement.option_ids:
            expanded |= self._equivalents.get(course_id, set())
        return frozenset(expanded)

    def _build_edges(
        self, course_ids: list[int], designations: dict[int, str]
    ) -> dict[int, list[RequirementView]]:
        """course id to every requirement it could fill, in program order."""
        edges: dict[int, list[RequirementView]] = {}
        for course_id in course_ids:
            course = self._courses.get(course_id)
            if course is None:
                continue
            designation = designations.get(course_id)
            allowed = [
                r for r in self._requirements if self._accepts(r, course, designation)
            ]
            if allowed:
                edges[course_id] = allowed
        return edges

    def edges_for(self, course_id: int, designation: str | None = None):
        """Which requirements one course could fill. Used by the analyzers."""
        course = self._courses.get(course_id)
        if course is None:
            return []
        return [r for r in self._requirements if self._accepts(r, course, designation)]

    # -- the matching ------------------------------------------------------
    def run(
        self,
        placed_course_ids: list[int],
        designations: dict[int, str] | None = None,
    ) -> AuditResult:
        designations = designations or {}
        # Where a student has both numbers of a cross-listed course, only one
        # can count. Take the lowest code so the result is deterministic; the
        # duplicate itself is reported separately as an error.
        chosen: dict[str, int] = {}
        singles: list[int] = []
        for course_id in placed_course_ids:
            course = self._courses.get(course_id)
            if course is None:
                continue
            if not course.equivalence_key:
                singles.append(course_id)
                continue
            current = chosen.get(course.equivalence_key)
            if current is None or course.code < self._courses[current].code:
                chosen[course.equivalence_key] = course_id
        candidates = sorted([*singles, *chosen.values()],
                            key=lambda cid: self._courses[cid].code)
        edges = self._build_edges(candidates, designations)

        assigned: dict[int, list[int]] = {r.id: [] for r in self._requirements}
        by_id = {r.id: r for r in self._requirements}

        def augment(course_id: int, visited: set[int]) -> bool:
            for requirement in edges.get(course_id, ()):
                if requirement.id in visited:
                    continue
                visited.add(requirement.id)
                holders = assigned[requirement.id]
                if len(holders) < requirement.slots:
                    holders.append(course_id)
                    return True
                # The row is full. See whether one of its current occupants can
                # move somewhere else, which frees a place here.
                for occupant in list(holders):
                    if augment(occupant, visited):
                        holders.remove(occupant)
                        holders.append(course_id)
                        return True
            return False

        matched: set[int] = set()
        for course_id in candidates:
            if augment(course_id, set()):
                matched.add(course_id)

        results = [
            RequirementResult(requirement=by_id[r.id], matched=sorted(assigned[r.id]))
            for r in self._requirements
        ]
        credits_matched = round(
            sum(self._courses[cid].credits for cid in matched), 2
        )
        credits_planned = round(
            sum(
                self._courses[cid].credits
                for cid in placed_course_ids
                if cid in self._courses
            ),
            2,
        )
        return AuditResult(
            requirements=results,
            unassigned=sorted(set(candidates) - matched),
            credits_required=round(sum(r.credits for r in self._requirements), 2),
            credits_matched=credits_matched,
            credits_planned=credits_planned,
        )


def build_requirement_views(program) -> list[RequirementView]:
    """Flatten a Program's groups into the flat list the matcher wants."""
    views: list[RequirementView] = []
    for group in program.groups:
        for requirement in group.requirements:
            views.append(
                RequirementView(
                    id=requirement.id,
                    group_position=group.position,
                    group_name=group.name,
                    group_notes=group.notes or "",
                    position=requirement.position,
                    label=requirement.label,
                    credits=requirement.credits,
                    slots=requirement.slots,
                    match_kind=requirement.match_kind,
                    option_ids=frozenset(
                        option.course_id for option in requirement.options
                    ),
                    subjects=tuple(
                        (requirement.pattern_subjects or "").split(",")
                        if requirement.pattern_subjects
                        else ()
                    ),
                    min_level=requirement.pattern_min_level,
                    slot_tag=requirement.slot_tag,
                    notes=requirement.notes or "",
                )
            )
    return views
