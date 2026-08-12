"""Shared fixtures for Conductor Again tests."""

import os
import sys
import pytest
import tempfile
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import MasterBase, ProjectBase, MasterSessionLocal, ensure_master_db
from app.models import User
from app.auth import hash_password
from app.database import get_project_engine

# Use temp DB for tests
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="conductor_test_")
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-32chars!"

from app.database import master_engine, MASTER_DB_PATH
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh test database before each test."""
    ensure_master_db()
    yield
    # Cleanup
    MasterBase.metadata.drop_all(bind=master_engine)


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
