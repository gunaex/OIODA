"""PM-E3 — PMStatus runtime + API."""

from app.contracts.validator import CanonicalContractValidator

_validator = CanonicalContractValidator("PMStatus")


def test_pm_status_fresh_project_is_not_started(auth_client):
    project = auth_client.post("/api/projects", json={"name": "PMStatus Fresh"}).json()
    slug = project["slug"]

    resp = auth_client.get(f"/api/{slug}/pm-status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["projectStatus"] == "NOT_STARTED"
    assert body["blockers"] == []
    _validator.validate(body)


def test_pm_status_reflects_blocked_task(auth_client):
    project = auth_client.post("/api/projects", json={"name": "PMStatus Blocked"}).json()
    slug = project["slug"]

    task = auth_client.post(f"/api/{slug}/tasks", json={"title": "Stuck task", "status": "Todo"}).json()
    auth_client.put(f"/api/{slug}/tasks/{task['id']}", json={"title": "Stuck task", "status": "Blocked"})

    resp = auth_client.get(f"/api/{slug}/pm-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["projectStatus"] == "BLOCKED"
    assert any(t["status"] == "Blocked" for t in body["tasks"])
    _validator.validate(body)


def test_pm_status_reflects_open_board_item_blocker(auth_client):
    project = auth_client.post("/api/projects", json={"name": "PMStatus Issue"}).json()
    slug = project["slug"]

    resp = auth_client.post(
        f"/api/{slug}/board-items",
        json={"item_type": "issue", "title": "Something broke", "status": "Open", "severity": "High"},
    )
    assert resp.status_code == 200, resp.text

    resp = auth_client.get(f"/api/{slug}/pm-status")
    body = resp.json()
    assert body["projectStatus"] == "BLOCKED"
    assert len(body["blockers"]) == 1
    assert body["blockers"][0]["description"] == "Something broke"
    _validator.validate(body)


def test_pm_status_completed_when_all_tasks_done(auth_client):
    project = auth_client.post("/api/projects", json={"name": "PMStatus Done"}).json()
    slug = project["slug"]
    task = auth_client.post(f"/api/{slug}/tasks", json={"title": "Finish it", "status": "Todo"}).json()
    auth_client.put(f"/api/{slug}/tasks/{task['id']}", json={"title": "Finish it", "status": "Done"})

    resp = auth_client.get(f"/api/{slug}/pm-status")
    body = resp.json()
    assert body["projectStatus"] == "COMPLETED"
    _validator.validate(body)


def test_pm_status_never_fabricates_estimated_completion_or_dependencies(auth_client):
    project = auth_client.post("/api/projects", json={"name": "PMStatus NoFab"}).json()
    slug = project["slug"]

    resp = auth_client.get(f"/api/{slug}/pm-status")
    body = resp.json()
    assert "estimatedCompletion" not in body
    assert "dependencies" not in body
