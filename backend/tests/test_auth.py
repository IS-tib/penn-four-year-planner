"""Registration, login and token handling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from app.config import settings
from app.models import User

from .conftest import Account


def test_register_returns_a_usable_token(client):
    account = Account(client, "new.student@upenn.edu")
    response = client.get("/api/auth/me", headers=account.headers)
    assert response.status_code == 200
    assert response.json()["email"] == "new.student@upenn.edu"


def test_register_does_not_guess_a_degree(client):
    # A plan belongs to a program and the app knows ten of them, so a new
    # account starts empty and is asked which one rather than assuming.
    account = Account(client, "starter@upenn.edu")
    assert client.get("/api/plans", headers=account.headers).json() == []


def test_duplicate_email_is_rejected(client):
    Account(client, "taken@upenn.edu")
    response = client.post(
        "/api/auth/register",
        json={"email": "taken@upenn.edu", "display_name": "Someone", "password": "another-pw-1"},
    )
    assert response.status_code == 409


def test_email_uniqueness_ignores_case(client):
    Account(client, "casing@upenn.edu")
    response = client.post(
        "/api/auth/register",
        json={"email": "CASING@upenn.edu", "display_name": "Dup", "password": "another-pw-1"},
    )
    assert response.status_code == 409


def test_login_accepts_a_differently_cased_email(client):
    account = Account(client, "mixed.case@upenn.edu")
    response = client.post(
        "/api/auth/login",
        json={"email": "Mixed.Case@UPenn.edu", "password": account.password},
    )
    assert response.status_code == 200


def test_login_rejects_a_wrong_password(client):
    account = Account(client, "wrongpw@upenn.edu")
    response = client.post(
        "/api/auth/login", json={"email": account.email, "password": "not-the-password"}
    )
    assert response.status_code == 401


def test_login_for_an_unknown_email_looks_the_same_as_a_wrong_password(client):
    response = client.post(
        "/api/auth/login", json={"email": "ghost@upenn.edu", "password": "whatever-123"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_password_is_never_stored_in_plaintext(client, db):
    account = Account(client, "hashing@upenn.edu", password="plaintext-check-9")
    stored = db.execute(
        select(User).where(User.email == account.email)
    ).scalar_one()
    assert stored.password_hash != account.password
    assert account.password not in stored.password_hash
    assert stored.password_hash.startswith("$2b$")


def test_short_passwords_are_rejected(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "short@upenn.edu", "display_name": "Short", "password": "abc123"},
    )
    assert response.status_code == 422


def test_passwords_longer_than_bcrypt_can_hash_are_rejected(client):
    # bcrypt only reads the first 72 bytes. Accepting a longer password would
    # make two different passwords interchangeable, so it is refused outright.
    response = client.post(
        "/api/auth/register",
        json={"email": "long@upenn.edu", "display_name": "Long", "password": "a" * 73},
    )
    assert response.status_code == 422


def test_blank_display_name_is_rejected(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "blank@upenn.edu", "display_name": "   ", "password": "valid-pass-1"},
    )
    assert response.status_code == 422


def test_protected_routes_need_a_token(client):
    assert client.get("/api/plans").status_code == 401
    assert client.get("/api/courses").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_a_malformed_token_is_rejected(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert response.status_code == 401


def test_a_token_signed_with_another_key_is_rejected(client, account):
    forged = jwt.encode(
        {
            "sub": str(account.id),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        "an-attackers-own-secret",
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_an_expired_token_is_rejected(client, account):
    expired = jwt.encode(
        {
            "sub": str(account.id),
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_a_token_for_a_deleted_account_is_rejected(client, db, account):
    stored = db.get(User, account.id)
    db.delete(stored)
    db.commit()
    response = client.get("/api/auth/me", headers=account.headers)
    assert response.status_code == 401
