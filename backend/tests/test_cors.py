"""Cross-origin preflight.

The frontend and the API are deployed to different origins, so every request
the browser makes that is not a simple GET or POST is preceded by a preflight
OPTIONS. If a method is missing from the CORS configuration the preflight fails
and the real request is never sent, which looks like a silent no-op in the
interface rather than an error anywhere.

This is exactly the bug that shipped once: PUT was left out of allow_methods, so
undo and redo did nothing in a browser while every test still passed, because
the test client does not preflight. These two tests are here so that cannot
happen again.
"""

from __future__ import annotations

import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.main import app

ORIGIN = settings.cors_origins[0]


def _cors_options() -> dict:
    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            return getattr(middleware, "kwargs", None) or getattr(middleware, "options", {})
    raise AssertionError("CORS middleware is not installed")


def _methods_the_api_serves() -> set[str]:
    used: set[str] = set()
    for route in app.routes:
        used |= set(getattr(route, "methods", None) or set())
    # HEAD is generated automatically alongside GET and is not something the
    # frontend ever asks for.
    return used - {"HEAD"}


def test_every_method_the_api_serves_is_allowed_by_cors():
    allowed = set(_cors_options()["allow_methods"])
    missing = _methods_the_api_serves() - allowed
    assert not missing, f"these methods would fail preflight from a browser: {sorted(missing)}"


@pytest.mark.parametrize("method", sorted(_methods_the_api_serves()))
def test_preflight_succeeds_for_each_method(client, method):
    response = client.options(
        "/api/plans/1/placements",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_a_foreign_origin_is_not_granted_access(client):
    response = client.options(
        "/api/plans/1/placements",
        headers={
            "Origin": "https://not-our-frontend.example",
            "Access-Control-Request-Method": "PUT",
        },
    )
    # Starlette answers the preflight but withholds the allow-origin header,
    # which is what makes the browser refuse the real request.
    assert "access-control-allow-origin" not in response.headers


def test_the_authorization_header_is_allowed(client):
    response = client.options(
        "/api/plans/1",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_the_bare_url_says_what_the_service_is(client):
    """A deployed API's root should not answer with a 404.

    Anyone pasting the API address into a browser sees this, and "Not Found"
    reads as a broken deployment rather than as a service with no root route.
    """
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Penn Four Year Planner API"
    assert body["docs"] == "/docs"
    assert body["health"] == "/api/health"


def test_the_health_check_render_uses_still_works(client):
    assert client.get("/api/health").json() == {"status": "ok"}
