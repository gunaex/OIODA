"""End-to-end Golden Flow integration test."""


class TestGoldenFlow:
    def test_full_golden_flow(self, client, auth_headers, test_project):
        """Vision → Decompose → Analyze → Deliberation readiness."""
        # Step 1: Create Vision
        resp = client.post(f"/api/{test_project}/vision", json={
            "content": "Build a Production BOM system with multi-level BOMs, "
                       "version history, approval workflows, circular reference detection, "
                       "Excel export, and ERP integration. Mobile-responsive UI.",
        }, headers=auth_headers)
        assert resp.status_code == 201

        # Step 2: Golden Flow trigger
        resp = client.post(f"/api/{test_project}/golden/trigger", json={
            "vision": "Build a Production BOM system with multi-level BOMs, "
                      "version history, approval workflows, circular reference detection, "
                      "Excel export, and ERP integration. Mobile-responsive UI.",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert "summary" in data
        assert data["summary"].startswith("Golden flow complete")

        # Verify steps
        steps = {s["step"]: s for s in data["steps"]}
        assert "vision_saved" in steps
        assert "requirements_extracted" in steps
        assert "functions_decomposed" in steps
        assert "risk_forecast" in steps

        # Step 3: Verify requirements were created
        resp = client.get(f"/api/{test_project}/requirements", headers=auth_headers)
        assert resp.status_code == 200
        reqs = resp.json()
        assert len(reqs) > 0

        # Step 4: Verify intake session
        resp = client.get(f"/api/{test_project}/intake/sessions", headers=auth_headers)
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) > 0

    def test_golden_flow_empty_vision(self, client, auth_headers, test_project):
        resp = client.post(f"/api/{test_project}/golden/trigger", json={
            "vision": "",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_ai_decompose(self, client, auth_headers, test_project):
        """AI-powered decomposition (falls back to rule-based without API key)."""
        resp = client.post(f"/api/{test_project}/golden/ai-decompose", json={
            "content": "1. User login\n2. Dashboard\n3. Reports",
            "source_type": "text",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["function_count"] == 3
        assert "ai_powered" in data
        # Without API key, should fall back to rule-based
        assert data["total_effort_days"] > 0
