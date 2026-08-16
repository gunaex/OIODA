"""Tests for Project Registry & Vision/Requirements."""


class TestProjects:
    def test_list_projects_empty(self, client, auth_headers):
        resp = client.get("/api/projects", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_project(self, client, auth_headers):
        resp = client.post("/api/projects", json={
            "slug": "my-project", "name": "My Project", "description": "Desc",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "my-project"
        assert data["name"] == "My Project"

    def test_create_duplicate_slug(self, client, auth_headers, test_project):
        resp = client.post("/api/projects", json={
            "slug": "test-project", "name": "Duplicate",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_update_project(self, client, auth_headers, test_project):
        resp = client.patch(f"/api/projects/{test_project}", json={
            "name": "Updated Name",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"


class TestVision:
    def test_create_vision(self, client, auth_headers, test_project):
        resp = client.post(f"/api/{test_project}/vision", json={
            "content": "Build an amazing product.",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["revision"] == 1
        assert data["content"] == "Build an amazing product."

    def test_list_visions(self, client, auth_headers, test_project):
        # Create two
        client.post(f"/api/{test_project}/vision", json={"content": "V1"}, headers=auth_headers)
        client.post(f"/api/{test_project}/vision", json={"content": "V2"}, headers=auth_headers)

        resp = client.get(f"/api/{test_project}/vision", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestRequirements:
    def test_create_requirement(self, client, auth_headers, test_project):
        resp = client.post(f"/api/{test_project}/requirements", json={
            "code": "REQ-001", "title": "User login", "description": "Email/password login",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["code"] == "REQ-001"

    def test_duplicate_code(self, client, auth_headers, test_project):
        client.post(f"/api/{test_project}/requirements", json={
            "code": "REQ-001", "title": "First",
        }, headers=auth_headers)
        resp = client.post(f"/api/{test_project}/requirements", json={
            "code": "REQ-001", "title": "Duplicate",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_list_requirements(self, client, auth_headers, test_project):
        client.post(f"/api/{test_project}/requirements", json={"code": "A", "title": "A"}, headers=auth_headers)
        client.post(f"/api/{test_project}/requirements", json={"code": "B", "title": "B"}, headers=auth_headers)
        resp = client.get(f"/api/{test_project}/requirements", headers=auth_headers)
        assert len(resp.json()) == 2
