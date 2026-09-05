"""Registration, login and identity."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Plan, User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import create_access_token, hash_password, verify_password
from ..services.ratelimit import limit_login, limit_register

router = APIRouter(prefix="/api/auth", tags=["auth"])

# A real bcrypt hash of a value nobody can log in with. When an email does not
# exist we still run a verify against it, so a wrong email and a wrong password
# take about the same time. Without this the response time alone tells an
# attacker which addresses have accounts.
_DUMMY_HASH = hash_password("not-a-real-password-placeholder")

_BAD_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_register)],
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = _normalize_email(payload.email)

    user = User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        ) from None

    # Give every new account something to open, so the first screen after
    # signing up is a plan rather than an empty state with a button.
    db.add(
        Plan(
            user_id=user.id,
            name="My Four Year Plan",
            start_year=datetime.now(timezone.utc).year,
        )
    )
    db.commit()
    db.refresh(user)
    return _issue(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limit_login)])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = _normalize_email(payload.email)
    user = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()

    if user is None:
        verify_password(payload.password, _DUMMY_HASH)
        raise _BAD_CREDENTIALS
    if not verify_password(payload.password, user.password_hash):
        raise _BAD_CREDENTIALS

    return _issue(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
