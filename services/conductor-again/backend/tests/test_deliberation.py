"""Tests for Multi-Agent Deliberation."""


class TestDeliberation:
    def test_start_deliberation_needs_resources(self, client, auth_headers):
        """Without AI resources, deliberation should fail with 400."""
        resp = client.post("/api/deliberation/start", json={
            "title": "Test deliberation",
            "trigger": "HIGH_IMPACT",
            "task": "Should we use A or B?",
            "criteria": "Performance, cost",
            "min_members": 1,
        }, headers=auth_headers)
        # Expect 400 because no AI resources exist
        assert resp.status_code == 400
        assert "available resources" in resp.json()["detail"].lower()

    def test_list_cases(self, client, auth_headers):
        resp = client.get("/api/deliberation", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_nonexistent_case(self, client, auth_headers):
        resp = client.get("/api/deliberation/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_submit_without_case(self, client, auth_headers):
        resp = client.post("/api/deliberation/nonexistent/submit", json={
            "member_id": "fake", "conclusion": "Test",
        }, headers=auth_headers)
        assert resp.status_code == 404
