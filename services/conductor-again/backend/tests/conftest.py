"""Shared fixtures for Conductor Again tests."""

import os
import sys
import pytest
import tempfile
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# MUST be set before ANY `app.*` import: app.database reads DATA_DIR at module
# import time into a module-level constant, so setting the env var afterward has
# no effect (pre-existing bug — every test run was silently writing Vision/
# Requirement/Project rows into the real backend/data/ directory instead of an
# isolated temp dir; test-project.db and my-project.db in backend/data/projects/
# were pollution from this and have been deleted as part of the E8 fix).
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="conductor_test_")
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-32chars!"
os.environ["TESTING"] = "true"

from app.database import MasterBase, ProjectBase, MasterSessionLocal, ensure_master_db
from app.models import User
from app.auth import hash_password
from app.database import get_project_engine, dispose_all_engines
from app.database import master_engine, MASTER_DB_PATH
from app.main import app
from fastapi.testclient import TestClient

# smoke_test.py, test_multi_ai.py (and ../test_smoke.py, excluded via pytest.ini's
# testpaths=tests) are standalone requests-based scripts meant to be run manually
# against a live server on :8000 with real seeded data/AI keys — they execute
# login/HTTP calls at module level, which crashes pytest collection rather than being
# a real test failure (pre-existing, E7-documented: "standalone, requests-based" /
# "module-level execution"). Excluded from collection rather than rewritten, since
# they are intentionally not pytest tests.
collect_ignore = ["smoke_test.py", "test_multi_ai.py"]


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh test database before each test.

    Per-project SQLite DBs are also reset every test (dispose engines + delete files):
    without this, project-scoped fixtures reusing the slug "test-project" across many
    test files leak Vision/Requirement rows between tests (pre-existing test-isolation
    gap, previously masked by the login rate limiter aborting most of these tests
    before their assertions ran)."""
    ensure_master_db()
    yield
    # Cleanup
    MasterBase.metadata.drop_all(bind=master_engine)
    dispose_all_engines()
    projects_dir = Path(os.environ["DATA_DIR"]) / "projects"
    if projects_dir.exists():
        for db_file in projects_dir.glob("*.db"):
            db_file.unlink(missing_ok=True)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def admin_user():
    """Create and return an admin user."""
    db = MasterSessionLocal()
    user = User(
        email="admin@test.com",
        password_hash=hash_password("TestPass123!"),
        display_name="Test Admin",
        role="admin",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def admin_token(client, admin_user):
    """Login and return access token."""
    resp = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "TestPass123!",
    })
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    """Authorization headers with admin token."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def test_project(client, auth_headers):
    """Create a test project and return its slug."""
    resp = client.post("/api/projects", json={
        "slug": "test-project",
        "name": "Test Project",
        "description": "A test project",
    }, headers=auth_headers)
    assert resp.status_code == 201
    return "test-project"
