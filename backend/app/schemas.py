"""Request and response shapes.

Pydantic validates every request body before a handler sees it, so the handlers
never have to check types, lengths or ranges themselves.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .security import MAX_PASSWORD_BYTES

MAX_TERMS = 12


# ---------------------------------------------------------------- auth ----


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


# ------------------------------------------------------------- catalog ----


class PrerequisiteGroupOut(BaseModel):
    codes: list[str]
    concurrent: bool


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    credits: float
    subject: str
    description: str = ""
    is_slot: bool = False
    slot_tag: str | None = None
    level: int | None = None
    min_term_index: int = 0
    prerequisite_text: str = ""
    prerequisite_codes: list[str] = []
    prerequisite_groups: list[PrerequisiteGroupOut] = []
    unlocks_codes: list[str] = []
    equivalent_codes: list[str] = []


class RequirementOut(BaseModel):
    id: int
    label: str
    credits: float
    slots: int
    match_kind: str
    slot_tag: str | None = None
    notes: str = ""
    option_codes: list[str] = []


class RequirementGroupOut(BaseModel):
    name: str
    notes: str = ""
    credits: float
    requirements: list[RequirementOut]


class ProgramOut(BaseModel):
    id: int
    code: str
    name: str
    degree: str
    school: str
    school_code: str
    total_units: float | None = None
    term_count: int
    tracks_full_degree: bool = True
    notes: str = ""
    source_url: str = ""


class ProgramDetail(ProgramOut):
    groups: list[RequirementGroupOut]


# --------------------------------------------------------------- plans ----


class PlanCreate(BaseModel):
    program_id: int
    name: str = Field(default="My Four Year Plan", min_length=1, max_length=120)
    start_year: int = Field(default=2026, ge=2000, le=2100)


class PlanRename(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PlacementCreate(BaseModel):
    course_id: int
    term_index: int = Field(ge=0, le=MAX_TERMS - 1)


class PlacementMove(BaseModel):
    term_index: int = Field(ge=0, le=MAX_TERMS - 1)


class PlacementInput(BaseModel):
    course_id: int
    term_index: int = Field(ge=0, le=MAX_TERMS - 1)
    fills_slot_tag: str | None = Field(default=None, max_length=40)


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


class PlacementOut(BaseModel):
    course_id: int
    term_index: int
    fills_slot_tag: str | None = None
    course: CourseOut


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


class AuditRequirementOut(BaseModel):
    id: int
    label: str
    credits: float
    slots: int
    filled_slots: int
    satisfied: bool
    match_kind: str
    slot_tag: str | None = None
    notes: str = ""
    matched_course_ids: list[int]


class AuditGroupOut(BaseModel):
    position: int
    name: str
    notes: str = ""
    credits: float
    satisfied: bool
    requirements: list[AuditRequirementOut]


class AuditOut(BaseModel):
    groups: list[AuditGroupOut]
    complete: bool
    satisfied_count: int
    requirement_count: int
    credits_required: float
    credits_matched: float
    credits_planned: float
    unassigned_course_ids: list[int]


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_year: int
    program_id: int


class PlanDetail(BaseModel):
    id: int
    name: str
    start_year: int
    share_token: str | None = None
    program: ProgramOut
    terms: list[TermOut]
    placements: list[PlacementOut]
    diagnostics: list[DiagnosticOut]
    audit: AuditOut
    # Catalog courses some requirement of this degree would accept. The catalog
    # sidebar filters on it so a student is not handed all 209 courses at once.
    relevant_course_ids: list[int]
    total_planned_credits: float
    required_credits: float


class SharedPlanOut(BaseModel):
    """A shared plan as an outsider sees it.

    Deliberately not PlanDetail. That carries the plan id and the share token,
    and neither belongs in a response handed to whoever has the link.
    """

    name: str
    start_year: int
    owner_name: str
    program: ProgramOut
    terms: list[TermOut]
    placements: list[PlacementOut]
    diagnostics: list[DiagnosticOut]
    audit: AuditOut
    total_planned_credits: float
    required_credits: float


# ------------------------------------------------------------ features ----


class EligibleCourseOut(BaseModel):
    course_id: int
    code: str
    title: str
    credits: float
    subject: str
    is_slot: bool
    unlocks: int
    would_overload: bool
    counts_toward: str | None = None


class ShareOut(BaseModel):
    token: str
    path: str


class SwitchOut(BaseModel):
    """What changing to another program would cost."""

    program: ProgramOut
    verdict: str
    carried_over: list[CourseOut]
    wasted: list[CourseOut]
    carried_credits: float
    wasted_credits: float
    remaining_credits: float
    outstanding: int
    free_capacity: float
    extra_terms_from_load: int
    longest_remaining_chain: int
    extra_terms_from_chain: int
    min_extra_terms: int
    audit: AuditOut
