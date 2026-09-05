"""The sliding-window limiter, both on its own and on the login route."""

from __future__ import annotations

import pytest

from app.services.ratelimit import RateLimiter, login_limiter, register_limiter


def test_the_window_allows_exactly_the_limit():
    limiter = RateLimiter(limit=3, window_seconds=60, name="test")
    assert [limiter.check("a", now=0) for _ in range(3)] == [None, None, None]
    assert limiter.check("a", now=0) is not None


def test_the_window_slides_rather_than_resetting_on_a_fixed_boundary():
    limiter = RateLimiter(limit=2, window_seconds=60, name="test")
    limiter.check("a", now=0)
    limiter.check("a", now=30)
    assert limiter.check("a", now=40) is not None

    # At t=61 the first hit has aged out but the second has not, so exactly one
    # slot is free. A fixed-bucket limiter would have freed both.
    assert limiter.check("a", now=61) is None
    assert limiter.check("a", now=62) is not None
    assert limiter.check("a", now=91) is None


def test_the_retry_hint_counts_down_to_when_a_slot_frees():
    limiter = RateLimiter(limit=1, window_seconds=60, name="test")
    limiter.check("a", now=0)
    assert limiter.check("a", now=10) == pytest.approx(50.0)
    assert limiter.check("a", now=59) == pytest.approx(1.0)


def test_callers_are_counted_separately():
    limiter = RateLimiter(limit=1, window_seconds=60, name="test")
    assert limiter.check("first", now=0) is None
    assert limiter.check("second", now=0) is None
    assert limiter.check("first", now=0) is not None


def test_resetting_one_caller_leaves_the_others_alone():
    limiter = RateLimiter(limit=1, window_seconds=60, name="test")
    limiter.check("first", now=0)
    limiter.check("second", now=0)
    limiter.reset("first")
    assert limiter.check("first", now=0) is None
    assert limiter.check("second", now=0) is not None


def test_repeated_failed_logins_are_eventually_refused(client, account):
    original = login_limiter.limit
    login_limiter.limit = 4
    login_limiter.reset()
    try:
        for _ in range(4):
            response = client.post(
                "/api/auth/login",
                json={"email": account.email, "password": "wrong-password"},
            )
            assert response.status_code == 401

        blocked = client.post(
            "/api/auth/login",
            json={"email": account.email, "password": "wrong-password"},
        )
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
        assert int(blocked.headers["Retry-After"]) > 0
        assert "Too many sign in attempts" in blocked.json()["detail"]

        # The correct password does not get a free pass either, which is the
        # point: the limit is on attempts, not on failures.
        assert client.post(
            "/api/auth/login",
            json={"email": account.email, "password": account.password},
        ).status_code == 429
    finally:
        login_limiter.limit = original
        login_limiter.reset()


def test_registration_is_limited_too(client):
    original = register_limiter.limit
    register_limiter.limit = 2
    register_limiter.reset()
    try:
        for index in range(2):
            response = client.post(
                "/api/auth/register",
                json={
                    "email": f"limited-{index}@upenn.edu",
                    "display_name": "Test",
                    "password": "a-good-password-1",
                },
            )
            assert response.status_code == 201

        blocked = client.post(
            "/api/auth/register",
            json={
                "email": "limited-3@upenn.edu",
                "display_name": "Test",
                "password": "a-good-password-1",
            },
        )
        assert blocked.status_code == 429
    finally:
        register_limiter.limit = original
        register_limiter.reset()


def test_the_limiter_keys_on_the_forwarded_address(client):
    """Behind a proxy the socket address is the proxy's, so the header decides."""
    original = register_limiter.limit
    register_limiter.limit = 1
    register_limiter.reset()
    try:
        first = client.post(
            "/api/auth/register",
            json={
                "email": "proxy-a@upenn.edu",
                "display_name": "A",
                "password": "a-good-password-1",
            },
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        assert first.status_code == 201

        # Same forwarded address, so it is refused.
        assert client.post(
            "/api/auth/register",
            json={
                "email": "proxy-b@upenn.edu",
                "display_name": "B",
                "password": "a-good-password-1",
            },
            headers={"X-Forwarded-For": "203.0.113.10"},
        ).status_code == 429

        # A different one is a different caller.
        assert client.post(
            "/api/auth/register",
            json={
                "email": "proxy-c@upenn.edu",
                "display_name": "C",
                "password": "a-good-password-1",
            },
            headers={"X-Forwarded-For": "203.0.113.99, 10.0.0.1"},
        ).status_code == 201
    finally:
        register_limiter.limit = original
        register_limiter.reset()


def test_reading_a_plan_is_not_rate_limited(account):
    for _ in range(30):
        response = account.client.get(
            f"/api/plans/{account.default_plan_id}", headers=account.headers
        )
        assert response.status_code == 200
