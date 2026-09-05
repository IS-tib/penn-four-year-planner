"""The public read-only view of a shared plan.

This is the one part of the API that takes no Authorization header. A student
sends the link to an advisor or a friend, who should be able to open it without
making an account. Everything about it is deliberately narrow: it is GET only,
the token is the entire credential, and the response carries the plan and the
owner's display name but never their email or their other plans.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Plan
from ..schemas import SharedPlanOut
from ..services.plans import serialize_plan

router = APIRouter(prefix="/api/shared", tags=["shared"])


@router.get("/{token}", response_model=SharedPlanOut)
def read_shared_plan(token: str, db: Session = Depends(get_db)) -> dict:
    # Look the plan up by token only. There is deliberately no endpoint that
    # takes a plan id here, because that would let anyone walk the ids.
    plan = db.execute(
        select(Plan).where(Plan.share_token == token)
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That share link is not valid. It may have been revoked.",
        )

    detail = serialize_plan(db, plan)
    return {
        "name": detail["name"],
        "start_year": detail["start_year"],
        "owner_name": plan.owner.display_name,
        "terms": detail["terms"],
        "placements": detail["placements"],
        "diagnostics": detail["diagnostics"],
        "progress": detail["progress"],
        "total_planned_credits": detail["total_planned_credits"],
        "degree_total_credits": detail["degree_total_credits"],
        "published_degree_credits": detail["published_degree_credits"],
    }
