"""BASELINE_PM_CORE_TESTS — safety net over existing PM behavior, captured
before ecosystem changes. Not exhaustive router coverage by design (see
PM-E1 plan): health, auth, project CRUD, task CRUD, dashboard, and
project-DB isolation."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_requires_valid_credentials(client, admin_user):
    resp = client.post("/api/auth/login", json={"email": "pmo@test.local", "password": "wrong-password"})
    assert resp.status_code == 401

    resp = client.post("/api/auth/login", json={"email": "pmo@test.local", "password": "test-password-123"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "pmo@test.local"


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 401


def test_me_reflects_logged_in_user(auth_client):
    resp = auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "pmo@test.local"


def test_project_create_and_read(auth_client):
    resp = auth_client.post("/api/projects", json={"name": "Baseline Project", "project_type": "simple"})
    assert resp.status_code == 200, resp.text
    project = resp.json()
    assert project["name"] == "Baseline Project"
    slug = project["slug"]

    resp = auth_client.get(f"/api/projects/{slug}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == slug

    resp = auth_client.get("/api/projects")
    assert resp.status_code == 200
    assert any(p["slug"] == slug for p in resp.json())


def test_task_create_read_update(auth_client):
    project = auth_client.post("/api/projects", json={"name": "Task Project"}).json()
    slug = project["slug"]

    resp = auth_client.post(f"/api/{slug}/tasks", json={"title": "Do the thing", "status": "Todo"})
    assert resp.status_code == 200, resp.text
    task = resp.json()
    assert task["title"] == "Do the thing"
    assert task["status"] == "Todo"

    resp = auth_client.get(f"/api/{slug}/tasks")
    assert resp.status_code == 200
    assert any(t["id"] == task["id"] for t in resp.json())

    resp = auth_client.put(f"/api/{slug}/tasks/{task['id']}", json={"title": "Do the thing", "status": "InProgress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "InProgress"


def test_project_dashboard_reads(auth_client):
    project = auth_client.post("/api/projects", json={"name": "Dashboard Project"}).json()
    slug = project["slug"]

    resp = auth_client.get(f"/api/{slug}/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == slug
    assert body["rag"] in ("red", "amber", "green")


def test_project_db_isolation(auth_client):
    """Two projects' tasks never leak into one another — the core guarantee
    of the per-project SQLite file design (database.py get_project_engine)."""
    project_a = auth_client.post("/api/projects", json={"name": "Isolation A"}).json()
    project_b = auth_client.post("/api/projects", json={"name": "Isolation B"}).json()

    auth_client.post(f"/api/{project_a['slug']}/tasks", json={"title": "Only in A"})
    auth_client.post(f"/api/{project_b['slug']}/tasks", json={"title": "Only in B"})

    tasks_a = auth_client.get(f"/api/{project_a['slug']}/tasks").json()
    tasks_b = auth_client.get(f"/api/{project_b['slug']}/tasks").json()

    assert [t["title"] for t in tasks_a] == ["Only in A"]
    assert [t["title"] for t in tasks_b] == ["Only in B"]
