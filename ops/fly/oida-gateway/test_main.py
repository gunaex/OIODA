import unittest

from main import _upstream_path


class UpstreamPathContractTests(unittest.TestCase):
    def test_infra_health_uses_root_probe(self):
        self.assertEqual(_upstream_path("infra", "health", "/api/v1"), "/health")

    def test_infra_business_routes_remain_versioned(self):
        self.assertEqual(
            _upstream_path("infra", "designs", "/api/v1"),
            "/api/v1/designs",
        )

    def test_other_bounded_services_keep_api_prefix(self):
        self.assertEqual(_upstream_path("pm", "projects", "/api"), "/api/projects")


if __name__ == "__main__":
    unittest.main()
