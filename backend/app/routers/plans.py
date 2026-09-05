"""Plans, the courses placed inside them, and the analyses over them."""

from __future__ import annotations

import csv
import io
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user, get_owned_plan
from ..models import Course, Plan, PlanCourse, Program, RequirementGroup, User
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
    SwitchOut,
)
from ..services.audit import DegreeAudit, build_requirement_views
from ..services.autofill import autofill_plan
from ..services.compare import analyse_switch, verdict
from ..services.eligibility import EligibilityFinder
from ..services.planner import equivalence_map
from ..services.plans import (
    audit_payload,
    course_payload,
    load_courses,
    load_dependents,
    load_prerequisites,
    program_payload,
    serialize_plan,
)

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _placements(db: Session, plan: Plan):
    return db.execute(select(PlanCourse).where(PlanCourse.plan_id == plan.id)).scalars().all()


def _maps(db: Session, plan: Plan) -> tuple[dict[int, int], dict[int, str]]:
    rows = _placements(db, plan)
    return (
        {row.course_id: row.term_index for row in rows},
        {row.course_id: row.fills_slot_tag for row in rows if row.fills_slot_tag},
    )


# ------------------------------------------------------------ plan CRUD ---


@router.get("", response_model=list[PlanSummary])
def list_plans(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Plan]:
    return list(
        db.execute(select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at))
        .scalars()
        .all()
    )


@router.post("", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    program = db.get(Program, payload.program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    plan = Plan(
        user_id=user.id,
        program_id=program.id,
        name=payload.name,
        start_year=payload.start_year,
    )
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
def delete_plan(plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)) -> Response:
    db.delete(plan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------- placements ---


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
    if payload.term_index >= plan.program.term_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This plan has {plan.program.term_count} terms",
        )

    db.add(PlanCourse(plan_id=plan.id, course_id=course.id, term_index=payload.term_index))
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
    if payload.term_index >= plan.program.term_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This plan has {plan.program.term_count} terms",
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
    wanted = {item.course_id: item for item in payload.placements}
    if len(wanted) != len(payload.placements):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A course can only appear once in a plan",
        )
    for item in payload.placements:
        if item.term_index >= plan.program.term_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"This plan has {plan.program.term_count} terms",
            )

    known = (
        {
            row.id
            for row in db.execute(select(Course).where(Course.id.in_(wanted))).scalars()
        }
        if wanted
        else set()
    )
    unknown = sorted(set(wanted) - known)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown course ids: {unknown}"
        )

    for row in _placements(db, plan):
        db.delete(row)
    db.flush()
    db.add_all(
        PlanCourse(
            plan_id=plan.id,
            course_id=item.course_id,
            term_index=item.term_index,
            fills_slot_tag=item.fills_slot_tag,
        )
        for item in wanted.values()
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

    The point of this is slots. A student lays out four years with "Social
    Science or Humanities III" in the sixth term, later decides that slot is
    a specific course, and wants it in the same place. The replacement inherits
    the slot's tag, which is how the audit knows an arbitrary course counts
    toward a requirement the catalog never enumerated.
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
    if db.execute(
        select(PlanCourse).where(
            PlanCourse.plan_id == plan.id, PlanCourse.course_id == replacement.id
        )
    ).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{replacement.code} is already in this plan",
        )

    outgoing = db.get(Course, course_id)
    term = placement.term_index
    inherited = placement.fills_slot_tag or (outgoing.slot_tag if outgoing else None)
    db.delete(placement)
    db.flush()
    db.add(
        PlanCourse(
            plan_id=plan.id,
            course_id=replacement.id,
            term_index=term,
            fills_slot_tag=None if replacement.is_slot else inherited,
        )
    )
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


# ------------------------------------------------------------ analyses ---


@router.post("/{plan_id}/autofill", response_model=PlanDetail)
def autofill(plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)) -> dict:
    autofill_plan(db, plan)
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.get("/{plan_id}/eligible", response_model=list[EligibleCourseOut])
def eligible_courses(
    term_index: int = Query(ge=0, le=11),
    subject: str | None = Query(default=None, max_length=12),
    slot_tag: str | None = Query(default=None, max_length=40),
    exclude_slots: bool = Query(default=False),
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Every course that could legally be added to the given term."""
    if term_index >= plan.program.term_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This plan has {plan.program.term_count} terms",
        )

    courses = load_courses(db)
    prereqs = load_prerequisites(db)
    placements, designations = _maps(db, plan)

    # Which courses would help fill something still outstanding, so the picker
    # can lead with them instead of an alphabetical dump.
    requirements = build_requirement_views(plan.program)
    audit_engine = DegreeAudit(requirements, courses, equivalence_map(courses))
    result = audit_engine.run(list(placements), designations)
    wanted: dict[int, str] = {}
    for row in result.requirements:
        if row.satisfied:
            continue
        for course_id in courses:
            if course_id in placements:
                continue
            if row.requirement in audit_engine.edges_for(course_id):
                wanted.setdefault(course_id, row.requirement.label)

    finder = EligibilityFinder(courses, prereqs)
    found = finder.find(
        placements,
        term_index,
        subject=subject.upper() if subject else None,
        slot_tag=slot_tag,
        exclude_slots=exclude_slots,
        wanted=wanted,
    )
    return [vars(item) for item in found]


@router.get("/{plan_id}/switch/{program_code}", response_model=SwitchOut)
def switch_analysis(
    program_code: str,
    plan: Plan = Depends(get_owned_plan),
    db: Session = Depends(get_db),
) -> dict:
    """What switching this plan to another degree would cost."""
    target = (
        db.execute(
            select(Program)
            .where(Program.code == program_code)
            .options(
                selectinload(Program.school),
                selectinload(Program.groups).selectinload(RequirementGroup.requirements),
            )
        )
        .scalars()
        .unique()
        .one_or_none()
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    courses = load_courses(db)
    prereqs = load_prerequisites(db)
    equivalents = equivalence_map(courses)
    placements, designations = _maps(db, plan)

    analysis = analyse_switch(
        build_requirement_views(target),
        courses,
        prereqs,
        equivalents,
        placements,
        designations,
        target.term_count,
    )

    course_rows = {row.id: row for row in db.execute(select(Course)).scalars().all()}
    dependents = load_dependents(prereqs)

    def payload(ids: list[int]) -> list[dict]:
        return [
            course_payload(course_rows[cid], prereqs, courses, dependents, equivalents)
            for cid in ids
        ]

    return {
        "program": program_payload(target),
        "verdict": verdict(analysis),
        "carried_over": payload(analysis.carried_over),
        "wasted": payload(analysis.wasted),
        "carried_credits": analysis.carried_credits,
        "wasted_credits": analysis.wasted_credits,
        "remaining_credits": analysis.remaining_credits,
        "outstanding": analysis.outstanding,
        "free_capacity": analysis.free_capacity,
        "extra_terms_from_load": analysis.extra_terms_from_load,
        "longest_remaining_chain": analysis.longest_remaining_chain,
        "extra_terms_from_chain": analysis.extra_terms_from_chain,
        "min_extra_terms": analysis.min_extra_terms,
        "audit": audit_payload(analysis.audit),
    }


# ------------------------------------------------------- share and export -


@router.post("/{plan_id}/share", response_model=ShareOut)
def create_share_link(
    plan: Plan = Depends(get_owned_plan), db: Session = Depends(get_db)
) -> ShareOut:
    """Mint a read-only link, or return the existing one.

    The token is the only thing standing between the public and this plan, so
    it comes from secrets rather than anything derived from the plan id, and it
    is long enough that guessing is not a strategy. Calling this twice returns
    the same link so a shared URL does not quietly stop working.
    """
    if not plan.share_token:
        plan.share_token = secrets.token_urlsafe(24)
        db.commit()
        db.refresh(plan)
    return ShareOut(token=plan.share_token, path=f"/shared/{plan.share_token}")


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
    writer.writerow(["Term", "Course", "Title", "Course Units", "Fills"])
    for entry in detail["placements"]:
        course = entry["course"]
        writer.writerow(
            [
                labels.get(entry["term_index"], entry["term_index"]),
                course["code"],
                course["title"],
                course["credits"],
                entry["fills_slot_tag"] or "",
            ]
        )
    writer.writerow([])
    writer.writerow(["Program", detail["program"]["name"], detail["program"]["degree"], "", ""])
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
