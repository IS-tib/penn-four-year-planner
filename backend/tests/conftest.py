"""Test fixtures.

The database URL and secret are set before the app package is imported, because
config.py reads the environment once at import time. Each test then gets a
freshly created and freshly seeded database.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="planner-tests-"))
os.environ["SECRET_KEY"] = "test-secret-key-not-used-anywhere-real"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ratelimit import login_limiter, register_limiter  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Every test starts with an empty rate-limit window.

    The whole suite comes from one client address, so without this the tenth
    test to register an account would start getting 429s. The limiter itself is
    tested directly in test_ratelimit.py rather than by accident here.
    """
    login_limiter.reset()
    register_limiter.reset()
    yield
    login_limiter.reset()
    register_limiter.reset()


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    # The app's lifespan creates the tables and seeds the catalog.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    with SessionLocal() as session:
        yield session


class Account:
    """A registered user, their headers, and a plan to work in."""

    def __init__(
        self,
        client: TestClient,
        email: str,
        password: str = "correct-horse-1",
        program: str = "CIS-BSE",
    ):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "display_name": email.split("@")[0], "password": password},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        self.client = client
        self.email = email
        self.password = password
        self.token = body["access_token"]
        self.id = body["user"]["id"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self._programs: dict[str, dict] = {}
        self._plan_id: int | None = None
        self.program_code = program

    # -- programs ---------------------------------------------------------
    def programs(self) -> dict[str, dict]:
        if not self._programs:
            rows = self.client.get("/api/programs").json()
            self._programs = {row["code"]: row for row in rows}
        return self._programs

    def program(self, code: str) -> dict:
        return self.programs()[code]

    # -- plans ------------------------------------------------------------
    def new_plan(self, program: str = "CIS-BSE", name: str = "Test plan") -> dict:
        response = self.client.post(
            "/api/plans",
            json={
                "program_id": self.program(program)["id"],
                "name": name,
                "start_year": 2026,
            },
            headers=self.headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    @property
    def plan_id(self) -> int:
        if self._plan_id is None:
            self._plan_id = self.new_plan(self.program_code)["id"]
        return self._plan_id

    # kept as an alias so the intent reads clearly at call sites
    @property
    def default_plan_id(self) -> int:
        return self.plan_id

    def plan(self, plan_id: int | None = None) -> dict:
        return self.client.get(
            f"/api/plans/{plan_id or self.plan_id}", headers=self.headers
        ).json()

    # -- courses ----------------------------------------------------------
    def course_id(self, code: str) -> int:
        response = self.client.get(
            "/api/courses", params={"search": code}, headers=self.headers
        )
        assert response.status_code == 200, response.text
        for course in response.json():
            if course["code"] == code:
                return course["id"]
        raise AssertionError(f"{code} is not in the seeded catalog")

    def place(self, code: str, term: int, plan_id: int | None = None):
        return self.client.post(
            f"/api/plans/{plan_id or self.plan_id}/courses",
            json={"course_id": self.course_id(code), "term_index": term},
            headers=self.headers,
        )

    def autofill(self, plan_id: int | None = None) -> dict:
        response = self.client.post(
            f"/api/plans/{plan_id or self.plan_id}/autofill", headers=self.headers
        )
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture()
def account(client):
    return Account(client, "isabella@upenn.edu")


@pytest.fixture()
def other_account(client):
    return Account(client, "someone.else@upenn.edu")


def diagnostics(detail: dict, code: str) -> list[dict]:
    return [d for d in detail["diagnostics"] if d["code"] == code]


def errors(detail: dict) -> list[dict]:
    return [d for d in detail["diagnostics"] if d["severity"] == "error"]


def codes(detail: dict) -> set[str]:
    return {p["course"]["code"] for p in detail["placements"]}
