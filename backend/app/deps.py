"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Plan, User
from .security import TokenError, decode_access_token

# auto_error=False so a missing header produces our own 401 with a consistent
# body rather than FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    try:
        user_id = decode_access_token(credentials.credentials)
    except TokenError:
        raise _UNAUTHORIZED from None

    user = db.get(User, user_id)
    if user is None:
        # The token verified but the account is gone. Same response as a bad
        # token, so a deleted account cannot be distinguished from a bad one.
        raise _UNAUTHORIZED
    return user


def get_owned_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Plan:
    """Load a plan, but only if it belongs to the caller.

    Someone else's plan returns 404 rather than 403. A 403 would confirm that
    the id exists, which lets an attacker enumerate how many plans the service
    holds. There is no reason to leak that.
    """
    plan = db.get(Plan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan
