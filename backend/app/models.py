"""Database tables.

Two pieces of modelling here are worth reading before the rest.

**Prerequisites are stored in conjunctive normal form.** Penn states them as
boolean expressions, for example CIS 3200 needs "CIS 1210 AND CIS 2620" while
MATH 2400 needs "MATH 1410 OR MATH 1610". Rather than storing an expression
string and parsing it at validation time, each prerequisite row belongs to a
group: courses inside a group are OR'd, and the groups are AND'd. Every
prerequisite in the seeded catalog fits that shape, which makes validation a
plain loop instead of an expression evaluator.

**Degree requirements are data, not code.** A program is a row, its requirement
groups are rows, and each requirement is a row that knows how many slots it has
and what can fill them. Adding a degree is a seed-file change with no code
change, which is what lets one app serve engineering and arts and sciences
degrees that are structured completely differently.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    plans: Mapped[list["Plan"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------
# The catalog
# --------------------------------------------------------------------------


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    subject: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(600), default="")

    # Thousands band of the course number, for rules phrased as "2000 level or
    # above". Null for slots, which have no course number.
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cross-listed courses share a key. CIS 4480 and CIS 5480 are one course
    # with two numbers, so a plan holding both is counting it twice.
    equivalence_key: Mapped[str | None] = mapped_column(String(24), index=True, nullable=True)
    # Gates on class standing rather than on another course, e.g. senior design.
    min_term_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Where advising recommends a course sit, as opposed to where the catalog
    # permits it. Honoured by the scheduler, ignored by validation.
    preferred_term: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # A slot stands in for a requirement the student has not chosen a specific
    # course for yet, such as "Social Science or Humanities". Slots carry a tag
    # so an open requirement row knows which ones can fill it.
    is_slot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slot_tag: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)

    prerequisites: Mapped[list["Prerequisite"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        foreign_keys="Prerequisite.course_id",
    )

    __table_args__ = (CheckConstraint("credits >= 0", name="ck_courses_credits_nonnegative"),)


class Prerequisite(Base):
    """One course inside one OR-group of one course's prerequisites."""

    __tablename__ = "prerequisites"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    required_course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    # True where the catalog allows the requirement to be taken at the same
    # time, for example PHYS 0150 alongside MATH 1400.
    allow_concurrent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    course: Mapped[Course] = relationship(
        back_populates="prerequisites", foreign_keys=[course_id]
    )
    required_course: Mapped[Course] = relationship(foreign_keys=[required_course_id])

    __table_args__ = (
        UniqueConstraint(
            "course_id", "group_index", "required_course_id", name="uq_prereq_entry"
        ),
    )


# --------------------------------------------------------------------------
# Degrees
# --------------------------------------------------------------------------


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    programs: Mapped[list["Program"]] = relationship(
        back_populates="school", cascade="all, delete-orphan"
    )


class Program(Base):
    """One degree, for example Computer Science BSE or Biology BA."""

    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    degree: Mapped[str] = mapped_column(String(12), nullable=False)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Course units the catalog prints for the degree. Null where the catalog
    # prints none, which happens for a major that cannot stand alone.
    total_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Terms a full plan spans. Eight for a standard four-year degree.
    term_count: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    # False for a major that is not a whole degree, such as a second major.
    # Full-time course-load warnings only make sense for a full degree: a
    # twelve unit second major legitimately leaves most of every term empty.
    tracks_full_degree: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str] = mapped_column(String(600), default="")
    source_url: Mapped[str] = mapped_column(String(300), default="")

    school: Mapped[School] = relationship(back_populates="programs")
    groups: Mapped[list["RequirementGroup"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="RequirementGroup.position",
    )


class RequirementGroup(Base):
    """A heading in the catalog's requirement table, such as "Engineering"."""

    __tablename__ = "requirement_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str] = mapped_column(String(600), default="")

    program: Mapped[Program] = relationship(back_populates="groups")
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="Requirement.position",
    )


# How a requirement decides which courses may fill it.
MATCH_EXPLICIT = "explicit"  # one of a listed set of courses
MATCH_PATTERN = "pattern"  # any course in a subject at or above a level
MATCH_SLOT = "slot"  # an open slot filled by a tagged placeholder


class Requirement(Base):
    """One row of a catalog requirement table.

    `slots` is how many courses the row consumes. Most rows are one course, so
    it is 1. "Select 4 Social Science or Humanities courses" is 4. Credits are
    tracked separately because Penn rows are priced in course units and a
    course can be 0.5, 1 or 1.5 of them.
    """

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_groups.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    slots: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    match_kind: Mapped[str] = mapped_column(String(12), nullable=False, default=MATCH_EXPLICIT)

    # For MATCH_PATTERN: comma separated subjects and a minimum level.
    pattern_subjects: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pattern_min_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # For MATCH_SLOT: which slot tag fills it.
    slot_tag: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str] = mapped_column(String(600), default="")

    group: Mapped[RequirementGroup] = relationship(back_populates="requirements")
    options: Mapped[list["RequirementOption"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("slots >= 1", name="ck_requirements_slots_positive"),
    )


class RequirementOption(Base):
    """One acceptable course for an explicit requirement.

    Several rows for one requirement means the catalog printed them as
    alternatives, for example "MATH 2400 or MATH 2600 or ESE 2030".
    """

    __tablename__ = "requirement_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )

    requirement: Mapped[Requirement] = relationship(back_populates="options")
    course: Mapped[Course] = relationship()

    __table_args__ = (
        UniqueConstraint("requirement_id", "course_id", name="uq_requirement_option"),
    )


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # Set when the owner creates a share link, cleared when they revoke it.
    # The token is the only credential for the public read-only view, so it is
    # generated from secrets and is long enough not to be guessable.
    share_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped[User] = relationship(back_populates="plans")
    program: Mapped[Program] = relationship()
    placements: Mapped[list["PlanCourse"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class PlanCourse(Base):
    """A course placed into a specific term of a specific plan."""

    __tablename__ = "plan_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    term_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Set when this course was chosen to fill an open requirement, for example
    # a real humanities course put into a "Social Science or Humanities" slot.
    # Without it the audit could not tell that CIS 3200 is not a humanities
    # course while ARTH 1000 is, since the catalog never prints the list.
    # Choosing is the student's, so the app records the choice rather than
    # guessing which requirement an arbitrary course ought to count for.
    fills_slot_tag: Mapped[str | None] = mapped_column(String(40), nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="placements")
    course: Mapped[Course] = relationship()

    __table_args__ = (
        # The database, not the request handler, is what guarantees a course
        # cannot land in two terms of the same plan. Two concurrent requests
        # can both pass an application-level check; only the constraint holds.
        UniqueConstraint("plan_id", "course_id", name="uq_plan_course_once"),
        CheckConstraint("term_index >= 0", name="ck_plan_courses_term_nonnegative"),
    )
