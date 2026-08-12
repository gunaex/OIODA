"""Tests for Intake & Decomposition Engine."""


class TestIntake:
    def test_parse_text(self, client, auth_headers, test_project):
        content = "1. User login\n2. Dashboard\n3. Export report"
        resp = client.post(f"/api/{test_project}/intake/parse", json={
            "content": content,
            "source_type": "text",
            "source_name": "Test Requirements",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["function_count"] == 3
        assert data["total_effort_person_days"] > 0
        assert "risk_forecast" in data
        assert "complexity_distribution" in data

    def test_parse_empty_content(self, client, auth_headers, test_project):
        resp = client.post(f"/api/{test_project}/intake/parse", json={
            "content": "", "source_type": "text",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_list_sessions(self, client, auth_headers, test_project):
        # Create one session first
        client.post(f"/api/{test_project}/intake/parse", json={
            "content": "1. Feature A", "source_type": "text",
        }, headers=auth_headers)

        resp = client.get(f"/api/{test_project}/intake/sessions", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_session_detail(self, client, auth_headers, test_project):
        # Create session
        r = client.post(f"/api/{test_project}/intake/parse", json={
            "content": "1. Feature X\n2. Feature Y", "source_type": "text",
        }, headers=auth_headers)
        session_id = r.json()["session_id"]

        resp = client.get(f"/api/{test_project}/intake/sessions/{session_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["functions"]) == 2
        assert data["risk"] is not None

    def test_complexity_analysis(self, client, auth_headers, test_project):
        """Complex text should get higher complexity scores."""
        resp = client.post(f"/api/{test_project}/intake/parse", json={
            "content": "1. Implement real-time streaming data pipeline with ETL, "
                       "multi-region failover, regulatory compliance audit trail, "
                       "and integration with 3 external APIs",
            "source_type": "text",
        }, headers=auth_headers)
        data = resp.json()
        assert len(data["functions"]) >= 1
        # Complex description should not be "trivial"
        if data["functions"]:
            cx = data["functions"][0]["complexity"]["level"]
            assert cx != "trivial"
