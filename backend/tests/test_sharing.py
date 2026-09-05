"""Read-only share links and CSV export."""

from __future__ import annotations


def _share(account):
    response = account.client.post(
        f"/api/plans/{account.default_plan_id}/share", headers=account.headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_sharing_returns_a_token_and_a_path(account):
    body = _share(account)
    assert len(body["token"]) >= 24
    assert body["path"] == f"/shared/{body['token']}"


def test_sharing_twice_returns_the_same_link(account):
    first = _share(account)["token"]
    second = _share(account)["token"]
    # A shared URL must not quietly stop working because the owner pressed the
    # button again.
    assert first == second


def test_the_token_appears_on_the_owners_plan(account):
    token = _share(account)["token"]
    detail = account.client.get(
        f"/api/plans/{account.default_plan_id}", headers=account.headers
    ).json()
    assert detail["share_token"] == token


def test_a_shared_plan_is_readable_without_any_credentials(client, account):
    account.place("CIS 1200", 0)
    token = _share(account)["token"]

    # No Authorization header at all.
    response = client.get(f"/api/shared/{token}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Test plan"
    assert body["owner_name"] == "isabella"
    assert [p["course"]["code"] for p in body["placements"]] == ["CIS 1200"]


def test_a_shared_plan_carries_its_checks_and_progress(client, account):
    account.place("CIS 1210", 0)
    token = _share(account)["token"]
    body = client.get(f"/api/shared/{token}").json()
    assert any(d["severity"] == "error" for d in body["diagnostics"])
    assert body["audit"]["requirement_count"] > 0
    assert body["required_credits"] == 37.0
    assert body["program"]["code"] == "CIS-BSE"


def test_a_shared_plan_does_not_leak_the_owners_email_or_ids(client, account):
    token = _share(account)["token"]
    body = client.get(f"/api/shared/{token}").json()
    assert "id" not in body
    assert "share_token" not in body
    assert account.email not in str(body)


def test_revoking_a_share_link_breaks_it(client, account):
    token = _share(account)["token"]
    assert client.get(f"/api/shared/{token}").status_code == 200

    revoke = account.client.delete(
        f"/api/plans/{account.default_plan_id}/share", headers=account.headers
    )
    assert revoke.status_code == 204
    assert client.get(f"/api/shared/{token}").status_code == 404


def test_an_unknown_token_is_a_404(client):
    assert client.get("/api/shared/not-a-real-token").status_code == 404


def test_sharing_does_not_expose_a_way_to_write(client, account):
    token = _share(account)["token"]
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)(f"/api/shared/{token}")
        assert response.status_code == 405, method


def test_only_the_owner_can_mint_or_revoke_a_link(account, other_account):
    victim = other_account.default_plan_id
    assert account.client.post(
        f"/api/plans/{victim}/share", headers=account.headers
    ).status_code == 404
    assert account.client.delete(
        f"/api/plans/{victim}/share", headers=account.headers
    ).status_code == 404


def test_two_plans_get_different_tokens(account):
    first = _share(account)["token"]
    second_plan = account.new_plan(name="Backup")["id"]
    second = account.client.post(
        f"/api/plans/{second_plan}/share", headers=account.headers
    ).json()["token"]
    assert first != second


def test_csv_export_lists_every_placement(account):
    account.place("CIS 1200", 0)
    account.place("MATH 1400", 1)
    response = account.client.get(
        f"/api/plans/{account.default_plan_id}/export.csv", headers=account.headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    lines = response.text.strip().splitlines()
    assert lines[0] == "Term,Course,Title,Course Units,Fills"
    assert any(line.startswith("Fall 2026,CIS 1200") for line in lines)
    assert any(line.startswith("Spring 2027,MATH 1400") for line in lines)
    assert lines[-1].startswith("Total planned")


def test_csv_export_sanitises_the_filename(account):
    account.client.patch(
        f"/api/plans/{account.default_plan_id}",
        json={"name": 'evil";\n drop'},
        headers=account.headers,
    )
    response = account.client.get(
        f"/api/plans/{account.default_plan_id}/export.csv", headers=account.headers
    )
    disposition = response.headers["content-disposition"]
    assert disposition == 'attachment; filename="evil-drop.csv"'
    assert "\n" not in disposition and disposition.count('"') == 2


def test_csv_export_is_scoped_to_the_owner(account, other_account):
    response = account.client.get(
        f"/api/plans/{other_account.default_plan_id}/export.csv", headers=account.headers
    )
    assert response.status_code == 404
