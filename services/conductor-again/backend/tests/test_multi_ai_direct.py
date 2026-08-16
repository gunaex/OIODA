"""Manual smoke script for multi-ai, run directly with `python test_multi_ai_direct.py`
against a project named `bom2` with a seeded admin user and real AI provider keys.
Guarded behind __main__ so pytest collection doesn't execute it as a real test
(E7 finding: this had a hardcoded Windows path and ran unconditionally at import
time, which crashed pytest collection on Mac)."""
import os
import sys


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    r = client.post("/api/auth/login", json={
        "email": "admin@conductoragain.local",
        "password": "ChangeMe123!",
    })
    h = {"Authorization": "Bearer " + r.json()["access_token"]}

    print("Calling Multi-AI...")
    r = client.post("/api/bom2/multi-ai/analyze", headers=h, json={
        "content": "Build a Production BOM system for a frozen food factory. Need: versioned BOM, approval workflow, circular reference detection.",
        "mode": "requirement",
        "panel_size": 2,
        "synthesize": False,
    })

    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Panel size: {data['panel_size']}")
        for i, p in enumerate(data["panel"]):
            label = chr(65 + i)
            err = p.get("error", "")
            content = (p.get("content") or err)[:200]
            tokens = p.get("tokens", {})
            print(f"  [{label}] {p['provider']}/{p['model']} ({tokens.get('input',0)}+{tokens.get('output',0)}tk, {p.get('latency_ms',0)}ms)")
            print(f"       {content}...")
        print("\nMULTI-AI TEST PASSED!")
    else:
        print(f"Error: {r.text[:500]}")


if __name__ == "__main__":
    main()
