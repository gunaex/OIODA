"""Test Multi-AI analysis with real AI (DeepSeek + Gemini)."""
import requests, json, time, sys

BASE = "http://127.0.0.1:8000/api"
r = requests.post(f"{BASE}/auth/login", json={
    "email": "admin@conductoragain.local",
    "password": "ChangeMe123!",
})
h = {"Authorization": "Bearer " + r.json()["access_token"]}

print("Sending to Multi-AI...")
t0 = time.time()
r = requests.post(f"{BASE}/bom2/multi-ai/analyze", headers=h, json={
    "content": "Build a Production BOM system for a frozen food factory. Requirements: versioned BOM, approval workflow, circular reference prevention, Excel import/export, yield calculation, allergen tracking.",
    "mode": "requirement",
    "panel_size": 3,
    "synthesize": True,
}, timeout=120)
elapsed = time.time() - t0
print(f"Status: {r.status_code} ({elapsed:.1f}s)")

if r.status_code != 200:
    print(f"Error: {r.text[:500]}")
    sys.exit(1)

data = r.json()
print(f"Panel size: {data['panel_size']}")
for i, p in enumerate(data["panel"]):
    label = chr(65 + i)
    status = "ERROR" if p.get("error") else "OK"
    tokens = p.get("tokens", {})
    preview = (p.get("content") or p.get("error") or "")[:100]
    print(f"  [{label}] {p['provider']}/{p['model']}: {status} "
          f"{tokens.get('input',0)}+{tokens.get('output',0)}tk "
          f"{p.get('latency_ms',0)}ms")
    print(f"       {preview}...")

if data.get("synthesis"):
    s = data["synthesis"]
    preview = (s.get("content") or s.get("error") or "")[:150]
    print(f"  Synthesis: {s['provider']}/{s['model']} "
          f"{s.get('latency_ms',0)}ms")
    print(f"       {preview}...")

print(f"\nDONE in {elapsed:.1f}s")
