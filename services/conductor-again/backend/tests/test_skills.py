"""Tests for Skill Registry & AUTO Router."""


class TestSkills:
    def test_create_skill(self, client, auth_headers):
        resp = client.post("/api/skills", json={
            "skill_id": "test-skill",
            "name": "Test Skill",
            "description": "A test skill",
            "category": "analysis",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["skill_id"] == "test-skill"
        assert data["status"] == "draft"
        return data["id"]

    def test_create_duplicate_skill_id(self, client, auth_headers):
        client.post("/api/skills", json={"skill_id": "dup", "name": "Dup"}, headers=auth_headers)
        resp = client.post("/api/skills", json={"skill_id": "dup", "name": "Dup2"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_list_skills(self, client, auth_headers):
        client.post("/api/skills", json={"skill_id": "s1", "name": "S1"}, headers=auth_headers)
        client.post("/api/skills", json={"skill_id": "s2", "name": "S2"}, headers=auth_headers)
        resp = client.get("/api/skills", headers=auth_headers)
        assert len(resp.json()) >= 2

    def test_create_version(self, client, auth_headers):
        # Create skill
        resp = client.post("/api/skills", json={"skill_id": "vtest", "name": "Version Test"}, headers=auth_headers)
        skill_id = resp.json()["id"]

        resp = client.post(f"/api/skills/{skill_id}/versions", json={
            "skill_db_id": skill_id,
            "system_instructions": "You are a test assistant.",
            "prompt_template": "Analyze: {{input}}",
            "release_notes": "Initial version",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == 1
        assert data["status"] == "draft"

    def test_publish_version(self, client, auth_headers):
        # Create skill + version
        resp = client.post("/api/skills", json={"skill_id": "pubtest", "name": "Publish Test"}, headers=auth_headers)
        skill_id = resp.json()["id"]
        resp = client.post(f"/api/skills/{skill_id}/versions", json={
            "skill_db_id": skill_id, "system_instructions": "Test", "prompt_template": "{{input}}",
        }, headers=auth_headers)
        version_id = resp.json()["id"]

        resp = client.post(f"/api/skills/versions/{version_id}/publish", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    def test_revoke_version(self, client, auth_headers):
        # Create skill + version + publish
        resp = client.post("/api/skills", json={"skill_id": "revtest", "name": "Revoke Test"}, headers=auth_headers)
        skill_id = resp.json()["id"]
        resp = client.post(f"/api/skills/{skill_id}/versions", json={
            "skill_db_id": skill_id, "system_instructions": "Test", "prompt_template": "{{input}}",
        }, headers=auth_headers)
        version_id = resp.json()["id"]

        resp = client.post(f"/api/skills/versions/{version_id}/revoke", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"

    def test_auto_router(self, client, auth_headers):
        """AUTO router should evaluate resources even if none eligible."""
        resp = client.post("/api/skills", json={"skill_id": "routetest", "name": "Router Test"}, headers=auth_headers)
        skill_id = resp.json()["id"]
        client.post(f"/api/skills/{skill_id}/versions", json={
            "skill_db_id": skill_id, "system_instructions": "Test", "prompt_template": "{{input}}",
        }, headers=auth_headers)

        resp = client.post("/api/skills/execute", json={
            "skill_id": "routetest",
            "project_slug": "",
            "input_data": {"test": True},
            "selection_mode": "AUTO",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "primary_resource_id" in data
        assert "candidates_considered" in data

    def test_filter_by_category(self, client, auth_headers):
        client.post("/api/skills", json={"skill_id": "cat_a", "name": "Cat A", "category": "analysis"}, headers=auth_headers)
        client.post("/api/skills", json={"skill_id": "cat_b", "name": "Cat B", "category": "vision"}, headers=auth_headers)

        resp = client.get("/api/skills?category=analysis", headers=auth_headers)
        assert resp.status_code == 200
        for s in resp.json():
            assert s["category"] == "analysis"
