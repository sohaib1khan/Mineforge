"""First-run setup and auth acceptance tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import login


def test_fresh_install_shows_setup_without_code(client: TestClient) -> None:
    status = client.get("/api/setup/status")
    assert status.status_code == 200
    assert status.json()["needs_setup"] is True

    ok = client.post(
        "/api/setup",
        json={
            "username": "admin_one",
            "password": "admin-password-12",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["role"] == "admin"

    status_after = client.get("/api/setup/status")
    assert status_after.json()["needs_setup"] is False


def test_setup_allows_dotted_username(client: TestClient) -> None:
    ok = client.post(
        "/api/setup",
        json={
            "username": "sohaib.khan",
            "password": "admin-password-12",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["username"] == "sohaib.khan"


def test_second_setup_attempt_rejected(client: TestClient) -> None:
    first = client.post(
        "/api/setup",
        json={
            "username": "admin_one",
            "password": "admin-password-12",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/setup",
        json={
            "username": "admin_two",
            "password": "admin-password-12",
        },
    )
    assert second.status_code == 409


def test_player_cannot_reach_admin_apis(
    client: TestClient, admin_user, player_user
) -> None:
    login(client, "player_one", "player-password-12")
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "player"
    csrf = me.json()["csrf_token"]

    users = client.get("/api/users")
    assert users.status_code == 403

    create = client.post(
        "/api/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "username": "player_two",
            "password": "player-password-12",
            "role": "player",
        },
    )
    assert create.status_code == 403

    audit = client.get("/api/audit")
    assert audit.status_code == 403


def test_admin_can_list_users(client: TestClient, admin_user, player_user) -> None:
    payload = login(client, "admin_one", "admin-password-12")
    assert payload["user"]["role"] == "admin"
    listed = client.get("/api/users")
    assert listed.status_code == 200
    usernames = {u["username"] for u in listed.json()["users"]}
    assert usernames == {"admin_one", "player_one"}


def test_change_own_password(client: TestClient, player_user) -> None:
    payload = login(client, "player_one", "player-password-12")
    csrf = payload["csrf_token"]
    response = client.post(
        "/api/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={
            "current_password": "player-password-12",
            "new_password": "new-player-pass-99",
        },
    )
    assert response.status_code == 200

    client.post("/api/auth/logout", headers={"X-CSRF-Token": payload["csrf_token"]})
    bad = client.post(
        "/api/auth/login",
        json={"username": "player_one", "password": "player-password-12"},
    )
    assert bad.status_code == 401
    good = client.post(
        "/api/auth/login",
        json={"username": "player_one", "password": "new-player-pass-99"},
    )
    assert good.status_code == 200
