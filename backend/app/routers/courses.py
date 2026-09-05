"""The course catalog."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Course, User
from ..deps import get_current_user
from ..schemas import CourseOut
from ..services.planner import equivalence_map
from ..services.plans import (
    course_payload,
    load_courses,
    load_dependents,
    load_prerequisites,
)

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=list[CourseOut])
def list_courses(
    search: str | None = Query(default=None, max_length=80),
    category: str | None = Query(default=None, max_length=40),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    stmt = select(Course)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Course.code.ilike(needle),
                Course.title.ilike(needle),
            )
        )
    if category:
        stmt = stmt.where(Course.category == category)

    rows = db.execute(stmt.order_by(Course.code)).scalars().all()
    prereqs = load_prerequisites(db)
    courses = load_courses(db)
    dependents = load_dependents(prereqs)
    equivalents = equivalence_map(courses)
    return [
        course_payload(row, prereqs, courses, dependents, equivalents) for row in rows
    ]
