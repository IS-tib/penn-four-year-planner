"""Request and response shapes.

Pydantic validates every request body before a handler sees it, so the handlers
below never have to check types, lengths or ranges themselves.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .config import settings
from .security import MAX_PASSWORD_BYTES


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"password must be at most {MAX_PASSWORD_BYTES} bytes once encoded"
            )
        return value

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display name cannot be blank")
        return cleaned


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class PrerequisiteGroupOut(BaseModel):
    """One OR-group. Satisfied by any of these, in an earlier term."""

    codes: list[str]
    concurrent: bool


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    credits: float
    department: str
    category: str
    description: str
    is_placeholder: bool
    level: int | None = None
    min_term_index: int = 0
    # Rendered prerequisite expression, for example "CIS 1200 and CIS 1600" or
    # "MATH 1410 or MATH 1610". Built from the prerequisite graph, not stored.
    prerequisite_text: str = ""
    prerequisite_codes: list[str] = []
    prerequisite_groups: list[PrerequisiteGroupOut] = []
    # What taking this course opens up, and the numbers it is cross-listed at.
    unlocks_codes: list[str] = []
    equivalent_codes: list[str] = []


class PlanCreate(BaseModel):
    name: str = Field(default="My Four Year Plan", min_length=1, max_length=120)
    start_year: int = Field(default=2026, ge=2000, le=2100)


class PlanRename(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PlacementCreate(BaseModel):
    course_id: int
    term_index: int = Field(ge=0, le=settings.terms_per_plan - 1)


class PlacementMove(BaseModel):
    term_index: int = Field(ge=0, le=settings.terms_per_plan - 1)


class PlacementOut(BaseModel):
    course_id: int
    term_index: int
    course: CourseOut


class PlacementInput(BaseModel):
    course_id: int
    term_index: int = Field(ge=0, le=settings.terms_per_plan - 1)


class PlacementsReplace(BaseModel):
    """The complete set of placements a plan should end up with.

    Undo and redo are built on this. Rather than replaying the inverse of every
    granular operation, which gets fiddly for something like autofill that
    touches twenty courses at once, the client keeps snapshots and asks the
    server to restore one. That makes undo a single atomic request whatever the
    operation was.
    """

    placements: list[PlacementInput] = Field(max_length=200)


class SwapRequest(BaseModel):
    replacement_course_id: int


class EligibleCourseOut(BaseModel):
    course_id: int
    code: str
    title: str
    credits: float
    category: str
    is_placeholder: bool
    unlocks: int
    would_overload: bool


class ShareOut(BaseModel):
    token: str
    path: str


class DiagnosticOut(BaseModel):
    severity: str
    code: str
    message: str
    course_code: str | None = None
    term_index: int | None = None


class TermOut(BaseModel):
    index: int
    label: str
    credits: float
    course_ids: list[int]


class CategoryProgressOut(BaseModel):
    category: str
    planned: float
    target: float


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_year: int


class PlanDetail(BaseModel):
    id: int
    name: str
    start_year: int
    share_token: str | None = None
    terms: list[TermOut]
    placements: list[PlacementOut]
    diagnostics: list[DiagnosticOut]
    progress: list[CategoryProgressOut]
    total_planned_credits: float
    # What the requirement buckets in this app add up to.
    degree_total_credits: float
    # What Penn publishes for the degree, which is one course unit more.
    published_degree_credits: float


class SharedPlanOut(BaseModel):
    """A shared plan as an outsider sees it.

    Deliberately not PlanDetail. That carries the plan id and the share token,
    and neither belongs in a response handed to whoever has the link. This
    shape is the read-only content and nothing else.
    """

    name: str
    start_year: int
    owner_name: str
    terms: list[TermOut]
    placements: list[PlacementOut]
    diagnostics: list[DiagnosticOut]
    progress: list[CategoryProgressOut]
    total_planned_credits: float
    degree_total_credits: float
    published_degree_credits: float
