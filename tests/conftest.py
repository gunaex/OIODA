"""Shared pytest fixtures for Account Again test suites (E3 + E4).

Introduced in E4: test_e3_acceptance.py and test_e4_credential_resolve.py both need to
override FastAPI's `get_db` dependency on the shared `app` singleton. Setting that
override at module-import time (as E3 originally did) is unsafe once a second test
module does the same thing — pytest imports every test module during collection before
running anything, so whichever module is imported last silently redirects the OTHER
module's requests to its own database. This file centralizes the override into a single
session-scoped fixture so both suites share one correctly-scoped test database.
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from account_again.database import Base, get_db
from account_again.main import app
import account_again.models  # noqa: ensure all models registered before create_all

test_db_path = os.path.join(os.path.dirname(__file__), "..", "test_account_again.db")
if os.path.exists(test_db_path):
    os.remove(test_db_path)
TEST_DB = f"sqlite:///{test_db_path}"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Reset DB state before each test."""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db_session = TestingSession()
    yield db_session
    db_session.close()
