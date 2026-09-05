"""Application configuration, read once at import time from the environment.

Everything that differs between a laptop and the deployed service lives here so
that no other module has to reach for os.environ.
"""

from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> tuple[str, ...]:
    raw = os.environ.get(name, default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    # A random per-process key keeps local development working without any
    # setup, at the cost of invalidating every issued token on restart. That
    # tradeoff is fine locally and unacceptable in production, so it warns.
    warnings.warn(
        "SECRET_KEY is not set. Generating an ephemeral key: issued tokens "
        "will stop working when this process restarts. Set SECRET_KEY in the "
        "deployment environment.",
        RuntimeWarning,
        stacklevel=2,
    )
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class Settings:
    secret_key: str = field(default_factory=_secret_key)
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./planner.db")
    algorithm: str = "HS256"
    access_token_ttl_minutes: int = int(os.environ.get("TOKEN_TTL_MINUTES", 60 * 24 * 7))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: _csv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    # Penn's standard full-time range is 4 to 5.5 course units a term; above
    # that needs an overload petition. These drive the term-load warnings.
    min_term_credits: float = 4.0
    max_term_credits: float = 5.5
    terms_per_plan: int = 8
    # What the autofill aims for per term before it starts using the headroom
    # up to the maximum. Roughly the degree total spread over eight terms, so a
    # generated plan is even rather than front-loaded.
    balanced_term_credits: float = 4.5


settings = Settings()
