"""Plans and the courses placed inside them."""

from __future__ import annotations

import csv
import io
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_owned_plan
from ..models import Course, Plan, PlanCourse, User
from ..schemas import (
    EligibleCourseOut,
    PlacementCreate,
    PlacementMove,
    PlacementsReplace,
    PlanCreate,
    PlanDetail,
    PlanRename,
    PlanSummary,
    ShareOut,
    SwapRequest,
)
from ..services.autofill import autofill_plan
from ..services.eligibility import EligibilityFinder
from ..services.plans import load_courses, load_prerequisites, serialize_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("", response_model=list[PlanSummary])
def list_plans(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Plan]:
    return list(
        db.execute(
            select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at)
        )
        .scalars()
        .all()
    )


@router.post("", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    plan = Plan(user_id=user.id, name=payload.name, start_year=payload.start_year)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.get("/{plan_id}", response_model=PlanDetail)
def get_plan(plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)) -> dict:
    return serialize_plan(db, plan)


@router.patch("/{plan_id}", response_model=PlanDetail)
def rename_plan(
    payload: PlanRename,
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> dict:
    plan.name = payload.name
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)
) -> Response:
    db.delete(plan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{plan_id}/courses", response_model=PlanDetail, status_code=status.HTTP_201_CREATED
)
def place_course(
    payload: PlacementCreate,
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> dict:
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    db.add(
        PlanCourse(plan_id=plan.id, course_id=course.id, term_index=payload.term_index)
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{course.code} is already in this plan",
        ) from None

    db.refresh(plan)
    return serialize_plan(db, plan)


@router.patch("/{plan_id}/courses/{course_id}", response_model=PlanDetail)
def move_course(
    course_id: int,
    payload: PlacementMove,
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> dict:
    placement = db.execute(
        select(PlanCourse).where(
            PlanCourse.plan_id == plan.id, PlanCourse.course_id == course_id
        )
    ).scalar_one_or_none()
    if placement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That course is not in this plan"
        )

    placement.term_index = payload.term_index
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.delete("/{plan_id}/courses/{course_id}", response_model=PlanDetail)
def remove_course(
    course_id: int,
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> dict:
    placement = db.execute(
        select(PlanCourse).where(
            PlanCourse.plan_id == plan.id, PlanCourse.course_id == course_id
        )
    ).scalar_one_or_none()
    if placement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That course is not in this plan"
        )

    db.delete(placement)
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/{plan_id}/autofill", response_model=PlanDetail)
def autofill(
    plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)
) -> dict:
    autofill_plan(db, plan, terms=settings.terms_per_plan)
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.put("/{plan_id}/placements", response_model=PlanDetail)
def replace_placements(
    payload: PlacementsReplace,
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> dict:
    """Replace every placement in the plan in one transaction.

    This is what undo and redo call. Doing it as one request rather than a
    stream of granular ones means a half-applied undo is not a state the plan
    can ever be in: either the whole snapshot is restored or none of it is.
    """
    wanted = {item.course_id: item.term_index for item in payload.placements}
    if len(wanted) != len(payload.placements):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A course can only appear once in a plan",
        )

    known = {
        row.id
        for row in db.execute(
            select(Course).where(Course.id.in_(wanted.keys()))
        ).scalars()
    } if wanted else set()
    unknown = sorted(set(wanted) - known)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown course ids: {unknown}",
        )

    for row in db.execute(
        select(PlanCourse).where(PlanCourse.plan_id == plan.id)
    ).scalars():
        db.delete(row)
    db.flush()

    db.add_all(
        PlanCourse(plan_id=plan.id, course_id=course_id, term_index=term)
        for course_id, term in wanted.items()
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.post("/{plan_id}/courses/{course_id}/swap", response_model=PlanDetail)
def swap_course(
    course_id: int,
    payload: SwapRequest,
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> dict:
    """Replace one course with another in the same term.

    The point of this is placeholder slots. A student lays out four years with
    "Technical Elective III" in the sixth term, then later decides that slot is
    CIS 5530, and wants it in the same place rather than having to remove and
    re-add and re-find the term.
    """
    placement = db.execute(
        select(PlanCourse).where(
            PlanCourse.plan_id == plan.id, PlanCourse.course_id == course_id
        )
    ).scalar_one_or_none()
    if placement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That course is not in this plan"
        )

    replacement = db.get(Course, payload.replacement_course_id)
    if replacement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Replacement course not found"
        )
    if replacement.id == course_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That course is already in this slot",
        )

    already = db.execute(
        select(PlanCourse).where(
            PlanCourse.plan_id == plan.id, PlanCourse.course_id == replacement.id
        )
    ).scalar_one_or_none()
    if already is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{replacement.code} is already in this plan",
        )

    term = placement.term_index
    db.delete(placement)
    db.flush()
    db.add(PlanCourse(plan_id=plan.id, course_id=replacement.id, term_index=term))
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.get("/{plan_id}/eligible", response_model=list[EligibleCourseOut])
def eligible_courses(
    term_index: int = Query(ge=0, le=settings.terms_per_plan - 1),
    category: str | None = Query(default=None, max_length=40),
    exclude_placeholders: bool = Query(default=False),
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Every course that could legally be added to the given term."""
    courses = load_courses(db)
    prereqs = load_prerequisites(db)
    placeholders = {
        row.id
        for row in db.execute(select(Course).where(Course.is_placeholder.is_(True))).scalars()
    }
    placements = {
        row.course_id: row.term_index
        for row in db.execute(
            select(PlanCourse).where(PlanCourse.plan_id == plan.id)
        ).scalars()
    }

    finder = EligibilityFinder(courses, prereqs, placeholders)
    found = finder.find(
        placements,
        term_index,
        category=category,
        exclude_placeholders=exclude_placeholders,
    )
    return [vars(item) for item in found]


@router.post("/{plan_id}/share", response_model=ShareOut)
def create_share_link(
    plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)
) -> ShareOut:
    """Mint a read-only link, or return the existing one.

    The token is the only thing standing between the public and this plan, so
    it comes from secrets rather than anything derived from the plan id, and it
    is long enough that guessing is not a strategy. Calling this twice returns
    the same link so that a shared URL does not quietly stop working.
    """
    if not plan.share_token:
        plan.share_token = secrets.token_urlsafe(24)
        db.commit()
        db.refresh(plan)
    return ShareOut(token=plan.share_token, path=f"/?share={plan.share_token}")


@router.delete("/{plan_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share_link(
    plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)
) -> Response:
    plan.share_token = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{plan_id}/export.csv")
def export_csv(plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)) -> Response:
    detail = serialize_plan(db, plan)
    labels = {term["index"]: term["label"] for term in detail["terms"]}

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Term", "Course", "Title", "Course Units", "Requirement"])
    for entry in detail["placements"]:
        course = entry["course"]
        writer.writerow(
            [
                labels[entry["term_index"]],
                course["code"],
                course["title"],
                course["credits"],
                course["category"],
            ]
        )
    writer.writerow([])
    writer.writerow(["Total planned", "", "", detail["total_planned_credits"], ""])

    filename = _safe_filename(plan.name) + ".csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_filename(name: str) -> str:
    """Keep a user-supplied plan name from steering the download header.

    A name containing a quote or a newline could otherwise break out of the
    Content-Disposition value, so only a known-safe alphabet survives.
    """
    cleaned = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in name).strip()
    return (cleaned or "plan").replace(" ", "-")[:60]
