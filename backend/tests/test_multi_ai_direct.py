"""Test multi-ai via TestClient with real AI response."""
import sys, os, json

os.chdir("d:/git/Conductor-Again/backend")
sys.path.insert(0, "d:/git/Conductor-Again/backend")

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Login
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
