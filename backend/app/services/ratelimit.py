"""A sliding-window rate limiter for the authentication endpoints.

Without this, a deployed instance is a free password oracle: bcrypt is slow
enough to make brute force expensive but not slow enough to make it impossible,
and nothing else stops an attacker from trying.

The state lives in this process's memory, which is the honest limitation. Two
web workers each get their own counters, so the effective limit is the
configured one multiplied by the worker count, and a restart forgets everything.
A real deployment would keep these counters in Redis so every worker sees the
same window. For a single free-tier instance this is the right amount of
machinery, and the interface below would not change if the storage did.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, name: str) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.name = name
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        # Handlers run in a thread pool, so two requests can touch the same
        # deque at once. The lock is what keeps the count from being wrong.
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> float | None:
        """Record an attempt. Returns seconds to wait if the caller is over."""
        moment = time.monotonic() if now is None else now
        cutoff = moment - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(0.0, hits[0] + self.window_seconds - moment)
            hits.append(moment)
            return None

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


def client_key(request: Request) -> str:
    """Identify the caller for rate-limiting purposes.

    Render and Vercel both sit behind a proxy, so the socket address is the
    proxy's. X-Forwarded-For is the only signal available, and it is trivially
    spoofable by anyone talking to the origin directly. That is acceptable
    here: the limiter raises the cost of a naive attack, and treating a forged
    header as a distinct client is no worse than having no limiter at all.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(limiter: RateLimiter, request: Request) -> None:
    retry_after = limiter.check(client_key(request))
    if retry_after is None:
        return
    seconds = max(1, int(retry_after) + 1)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many {limiter.name} attempts. Try again in {seconds} seconds.",
        headers={"Retry-After": str(seconds)},
    )


login_limiter = RateLimiter(limit=10, window_seconds=300, name="sign in")
register_limiter = RateLimiter(limit=5, window_seconds=3600, name="sign up")


def limit_login(request: Request) -> None:
    enforce(login_limiter, request)


def limit_register(request: Request) -> None:
    enforce(register_limiter, request)
