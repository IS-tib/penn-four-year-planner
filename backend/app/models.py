"""Database tables.

Prerequisite modelling is the one non-obvious piece here. Penn states
prerequisites as boolean expressions, for example CIS 3200 needs
"CIS 1210 AND CIS 2620" while CIS 5660 needs "CIS 4600 OR CIS 5600".

Rather than storing an expression string and parsing it at validation time,
prerequisites are stored in conjunctive normal form: each row belongs to a
group, courses inside a group are OR'd together, and the groups are AND'd.
So "CIS 1210 AND CIS 2620" is two single-member groups, and "CIS 4600 OR
CIS 5600" is one two-member group. Every prerequisite in the Penn catalog that
this app seeds fits that shape, and it makes validation a plain loop instead of
an expression evaluator.
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


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    department: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(600), default="")
    # Placeholders stand in for a requirement the student has not chosen a
    # specific course for yet, such as "Social Science or Humanities Elective".
    is_placeholder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Some courses gate on class standing rather than on another course. The
    # senior project needs senior standing, which no prerequisite edge can say,
    # so it is expressed as the earliest term the course may be taken.
    min_term_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Where Penn advising recommends a course sit, as opposed to where the
    # catalog permits it. CIS 1100 has no formal prerequisite relationship with
    # CIS 1200, but it is the introductory course and belongs in the first term.
    # The autofill honours this; validation deliberately ignores it, because an
    # advising convention is not a rule and should never raise an error.
    preferred_term: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The thousands band of the course number, so the degree rule capping
    # 1000-level CIS electives at one course unit can be checked. Null for
    # placeholder slots, which have no course number.
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cross-listed courses share a key. CIS 4480 and CIS 5480 are one course
    # with two numbers, so a plan holding both is counting it twice.
    equivalence_key: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)

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


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
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

    plan: Mapped[Plan] = relationship(back_populates="placements")
    course: Mapped[Course] = relationship()

    __table_args__ = (
        # The database, not the request handler, is what guarantees a course
        # cannot land in two terms of the same plan. Two concurrent requests
        # can both pass an application-level check; only the constraint holds.
        UniqueConstraint("plan_id", "course_id", name="uq_plan_course_once"),
        CheckConstraint("term_index >= 0", name="ck_plan_courses_term_nonnegative"),
    )
