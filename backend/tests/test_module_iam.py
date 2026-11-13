import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.iam_service import IAMService, PasswordValidationError

client = TestClient(app)


def test_password_strength_rules():
    # Less than 8 characters
    with pytest.raises(PasswordValidationError):
        IAMService.validate_password_strength("Pass1")

    # No digits
    with pytest.raises(PasswordValidationError):
        IAMService.validate_password_strength("PasswordOnly")

    # No letters
    with pytest.raises(PasswordValidationError):
        IAMService.validate_password_strength("123456789")

    # Valid corporate password
    IAMService.validate_password_strength("ValidPass2026!")


def test_iam_login_dual_token_issuance():
    # Attempt login with seeded staff account
    r = client.post("/api/v1/auth/login", json={"email": "abebe@abyssinia.et", "password": "Staff123!"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["refresh_token"]) > 20
    assert data["user"]["email"] == "abebe@abyssinia.et"
    assert data["user"]["role"] == "STAFF"


def test_iam_login_invalid_credentials():
    # Wrong password
    r = client.post("/api/v1/auth/login", json={"email": "abebe@abyssinia.et", "password": "WrongPassword99!"})
    assert r.status_code == 401

    # Non-existent email
    r_nonexistent = client.post("/api/v1/auth/login", json={"email": "ghost@abyssinia.et", "password": "AnyPassword123!"})
    assert r_nonexistent.status_code == 401


def test_iam_refresh_token_rotation():
    # 1. Login to get initial pair
    login_res = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
    assert login_res.status_code == 200
    initial_refresh_token = login_res.json()["refresh_token"]

    # 2. Rotate token
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh_token})
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    new_refresh_token = data["refresh_token"]
    assert new_refresh_token != initial_refresh_token

    # 3. Replay attack prevention: old refresh token must be rejected!
    replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh_token})
    assert replay_res.status_code == 401


def test_iam_session_management():
    # Login
    login_res = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # List active sessions
    sessions_res = client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    assert len(sessions) >= 1

    # Revoke a session
    target_session_id = sessions[0]["id"]
    revoke_res = client.post(f"/api/v1/auth/sessions/{target_session_id}/revoke", headers=headers)
    assert revoke_res.status_code == 200

    # Logout all devices
    logout_all_res = client.post("/api/v1/auth/logout-all", headers=headers)
    assert logout_all_res.status_code == 200
