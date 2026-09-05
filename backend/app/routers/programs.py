"""The degree programs this app knows about."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Program, RequirementGroup, School
from ..schemas import ProgramDetail, ProgramOut
from ..services.plans import program_payload

router = APIRouter(prefix="/api/programs", tags=["programs"])


def _loaded(db: Session):
    return select(Program).options(
        selectinload(Program.school),
        selectinload(Program.groups)
        .selectinload(RequirementGroup.requirements),
    )


@router.get("", response_model=list[ProgramOut])
def list_programs(db: Session = Depends(get_db)) -> list[dict]:
    """Public on purpose, so the landing page can show what is supported."""
    rows = (
        db.execute(_loaded(db).join(School).order_by(School.code, Program.name))
        .scalars()
        .unique()
        .all()
    )
    return [program_payload(program) for program in rows]


@router.get("/{code}", response_model=ProgramDetail)
def get_program(code: str, db: Session = Depends(get_db)) -> dict:
    program = (
        db.execute(_loaded(db).where(Program.code == code)).scalars().unique().one_or_none()
    )
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program_payload(program, include_requirements=True)
