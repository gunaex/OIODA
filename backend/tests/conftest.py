"""Test foundation. DATA_DIR is redirected to a fresh temp directory before
any `app.*` module is imported — main.py creates/seeds the master DB at
import time, so this must happen first or tests would touch the real
backend/data directory (see database.py's DATA_DIR / BASE_DIR)."""

import os
import shutil
import tempfile

import pytest

REAL_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="pm-again-test-")
os.environ["DATA_DIR"] = _TEST_DATA_DIR
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ADMIN_EMAIL"] = "test-admin@example.com"
os.environ["ADMIN_PASSWORD"] = "test-admin-password-123"
os.environ["COOKIE_SECURE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import models  # noqa: E402
from app.database import MasterSessionLocal  # noqa: E402
from app.auth import hash_password  # noqa: E402


def test_data_dir_never_touches_real_backend_data():
    """Guard test (TEST_DB_ISOLATION): proves the redirection above actually
    took effect, so no other test in this suite can silently fall back to
    writing into the real backend/data directory."""
    assert os.environ["DATA_DIR"] == _TEST_DATA_DIR
    assert os.path.abspath(_TEST_DATA_DIR) != os.path.abspath(REAL_DATA_DIR)
    from app import database

    assert os.path.abspath(database.DATA_DIR) == os.path.abspath(_TEST_DATA_DIR)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_data_dir():
    yield
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    from app.rate_limit import limiter

    limiter.reset()
    return TestClient(app)


@pytest.fixture()
def admin_user():
    """The bootstrap admin has must_change_password=True (by design — see
    seed.py). Tests need a ready-to-use internal user instead, created
    directly against the test master DB."""
    with MasterSessionLocal() as db:
        existing = db.query(models.User).filter(models.User.email == "pmo@test.local").first()
        if existing:
            return existing
        user = models.User(
            email="pmo@test.local",
            password_hash=hash_password("test-password-123"),
            role="pmo_admin",
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


@pytest.fixture()
def auth_client(client, admin_user):
    """A TestClient already logged in as a pmo_admin user (cookie-based, same
    as the browser flow)."""
    resp = client.post("/api/auth/login", json={"email": "pmo@test.local", "password": "test-password-123"})
    assert resp.status_code == 200, resp.text
    return client
