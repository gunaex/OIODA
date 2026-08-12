"""Tests for AI Resource Pool."""


class TestAIResources:
    def test_list_providers(self, client, auth_headers):
        resp = client.get("/api/ai/providers", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_provider(self, client, auth_headers):
        resp = client.post("/api/ai/providers", json={
            "code": "deepseek", "name": "DeepSeek",
            "website": "https://api.deepseek.com",
            "description": "DeepSeek AI",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["code"] == "deepseek"

    def test_create_duplicate_provider(self, client, auth_headers):
        client.post("/api/ai/providers", json={"code": "openai", "name": "OpenAI"}, headers=auth_headers)
        resp = client.post("/api/ai/providers", json={"code": "openai", "name": "OpenAI 2"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_pool_summary(self, client, auth_headers):
        resp = client.get("/api/ai/pool-summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_resources" in data
        assert "provider_count" in data

    def test_list_resources(self, client, auth_headers):
        resp = client.get("/api/ai/resources", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_account_no_key(self, client, auth_headers):
        """Create an account without API key."""
        # First create provider
        client.post("/api/ai/providers", json={"code": "test", "name": "Test Provider"}, headers=auth_headers)
        resp = client.get("/api/ai/providers", headers=auth_headers)
        provider_id = resp.json()[0]["id"]

        resp = client.post("/api/ai/accounts", json={
            "provider_id": provider_id,
            "name": "Test Account",
            "account_type": "api",
            "access_mode": "OFFICIAL_API",
            "api_base_url": "https://api.test.com",
            "api_key": "",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["api_key_last4"] == ""
