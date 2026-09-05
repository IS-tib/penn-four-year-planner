"""Password hashing and JSON Web Token issuing and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

# bcrypt hashes at most 72 bytes of input and silently ignores the rest, which
# would make two different long passwords interchangeable. The registration
# schema rejects anything longer, and this constant is what it checks against.
MAX_PASSWORD_BYTES = 72


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired or not ours."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # A stored hash that is not a valid bcrypt string should read as a
        # failed login rather than a 500.
        return False


def create_access_token(user_id: int) -> tuple[str, int]:
    """Return a signed token and the number of seconds until it expires."""
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> int:
    """Return the user id carried by a valid token, or raise TokenError."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            # Pinning the algorithm list is what stops a caller handing us a
            # token that claims alg "none" or a weaker algorithm.
            algorithms=[settings.algorithm],
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    subject = payload.get("sub")
    if subject is None:
        raise TokenError("token has no subject")
    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise TokenError("token subject is not a user id") from exc
