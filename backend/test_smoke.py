#!/usr/bin/env python
"""
Conductor Again — Smoke Test Suite
Tests the full API surface against a running server.
Run: python test_smoke.py
"""

import sys, time, requests

BASE = "http://127.0.0.1:8000/api"
PASS = FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok: PASS += 1; print(f"  ✅ {name}")
    else: FAIL += 1; print(f"  ❌ {name}: {detail}")

def j(r): return r.json()

print("=" * 60)
print("Conductor Again — Smoke Test Suite")
print("=" * 60)

# ── 1. Auth ──
print("\n📌 Auth")
r = requests.get(f"{BASE}/health")
check("Health check", r.status_code == 200)

r = requests.post(f"{BASE}/auth/login", json={"email": "admin@conductoragain.local", "password": "ChangeMe123!"})
token = j(r).get("access_token", "")
H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
check("Login", bool(token), r.text[:80])

r = requests.get(f"{BASE}/auth/me", headers=H)
check("Get me", r.status_code == 200, r.text[:80])

r = requests.post(f"{BASE}/auth/login", json={"email": "admin@conductoragain.local", "password": "wrong"})
check("Wrong password rejected", r.status_code == 401)

# ── 2. Projects ──
print("\n📌 Projects")
slug = f"smoke-{int(time.time()) % 10000}"

r = requests.post(f"{BASE}/projects", headers=H, json={"slug": slug, "name": "Smoke Test"})
check("Create project", r.status_code == 201, r.text[:80])

r = requests.get(f"{BASE}/projects", headers=H)
check("List projects", r.status_code == 200 and any(p["slug"] == slug for p in j(r)))

# ── 3. Vision ──
print("\n📌 Vision")
r = requests.post(f"{BASE}/{slug}/vision", headers=H, json={"content": "Build an amazing product."})
check("Create vision", r.status_code == 201)

r = requests.get(f"{BASE}/{slug}/vision", headers=H)
check("List visions", r.status_code == 200 and len(j(r)) >= 1)

# ── 4. Requirements ──
print("\n📌 Requirements")
r = requests.post(f"{BASE}/{slug}/requirements", headers=H, json={"code": "REQ-SMOKE-001", "title": "User Auth"})
check("Create requirement", r.status_code == 201)

r = requests.get(f"{BASE}/{slug}/requirements", headers=H)
check("List requirements", r.status_code == 200 and len(j(r)) >= 1)

# ── 5. AI Resources ──
print("\n📌 AI Resources")
r = requests.get(f"{BASE}/ai/providers", headers=H)
check("List providers", r.status_code == 200 and len(j(r)) >= 1, f"Got {len(j(r))} providers")

r = requests.get(f"{BASE}/ai/pool-summary", headers=H)
check("Pool summary", r.status_code == 200 and "total_resources" in j(r))

r = requests.get(f"{BASE}/ai/resources", headers=H)
check("List resources", r.status_code == 200 and isinstance(j(r), list))

# ── 6. Skills ──
print("\n📌 Skills")
r = requests.get(f"{BASE}/skills", headers=H)
skills = j(r)
check("List skills", r.status_code == 200 and len(skills) >= 1, f"Got {len(skills)} skills")

if skills:
    skill_id = skills[0]["skill_id"]
    r = requests.post(f"{BASE}/skills/execute", headers=H, json={"skill_id": skill_id, "selection_mode": "AUTO"})
    check("Execute AUTO router", r.status_code == 200 and "primary_resource_id" in j(r), r.text[:80])

# ── 7. Deliberation ──
print("\n📌 Deliberation")
r = requests.get(f"{BASE}/deliberation", headers=H)
check("List cases", r.status_code == 200 and isinstance(j(r), list))

# ── 8. Intake ──
print("\n📌 Intake")
r = requests.post(f"{BASE}/{slug}/intake/parse", headers=H, json={
    "content": "1. Feature A with complex workflow\n2. Feature B\n3. Feature C with API integration",
    "source_type": "text", "source_name": "Smoke Input",
})
data = j(r)
check("Parse text", r.status_code == 200 and data["function_count"] == 3 and data["total_effort_person_days"] > 0,
      f"Got {data.get('function_count')} functions, {data.get('total_effort_person_days')}d")

r = requests.get(f"{BASE}/{slug}/intake/sessions", headers=H)
check("List sessions", r.status_code == 200 and len(j(r)) >= 1)

# ── 9. Golden Flow ──
print("\n📌 Golden Flow")
r = requests.post(f"{BASE}/{slug}/golden/trigger", headers=H, json={
    "vision": "Build a Production BOM system with versioning, approval workflows, and ERP integration.",
})
data = j(r)
check("Golden Flow trigger", r.status_code == 200 and data.get("summary", "").startswith("Golden flow complete"),
      data.get("summary", "")[:60])

# ── 10. Storage ──
print("\n📌 Storage")
r = requests.get(f"{BASE}/{slug}/golden/storage/status", headers=H)
check("Storage status", r.status_code in (200, 503))

# ── Results ──
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed", end="")
if FAIL:
    print(f", {FAIL} failed ❌")
    sys.exit(1)
else:
    print(" — ALL PASSED ✅")
print("=" * 60)
