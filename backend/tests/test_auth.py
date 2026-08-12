"""Tests for Authentication & Authorization."""


class TestAuth:
    def test_login_success(self, client, admin_user):
        resp = client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, admin_user):
        resp = client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "WrongPassword",
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client):
        """Inactive users cannot login."""
        from app.database import MasterSessionLocal
        from app.models import User
        from app.auth import hash_password

        db = MasterSessionLocal()
        db.add(User(email="inactive@test.com", password_hash=hash_password("x"),
                     display_name="Inactive", role="viewer", active=False))
        db.commit()
        db.close()

        resp = client.post("/api/auth/login", json={
            "email": "inactive@test.com", "password": "x",
        })
        assert resp.status_code == 403

    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "admin@test.com"

    def test_me_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_logout(self, client, auth_headers):
        resp = client.post("/api/auth/logout", headers=auth_headers)
        assert resp.status_code == 200

    def test_change_password(self, client, auth_headers):
        resp = client.post("/api/auth/change-password", json={
            "current_password": "TestPass123!",
            "new_password": "NewPass456!",
        }, headers=auth_headers)
        assert resp.status_code == 200

    def test_change_password_wrong_current(self, client, auth_headers):
        resp = client.post("/api/auth/change-password", json={
            "current_password": "WrongPassword",
            "new_password": "NewPass456!",
        }, headers=auth_headers)
        assert resp.status_code == 400
