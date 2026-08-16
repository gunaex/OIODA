"""Quick smoke test — all critical endpoints."""
import requests, json, sys

BASE = "http://127.0.0.1:8000/api"
ok = 0
fail = 0

def test(name, method, path, **kw):
    global ok, fail
    try:
        r = method(f"{BASE}{path}", **kw)
        if r.status_code < 400:
            print(f"  PASS {name}: {r.status_code}")
            ok += 1
        else:
            print(f"  FAIL {name}: {r.status_code} {r.text[:100]}")
            fail += 1
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        fail += 1

# Login
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@conductoragain.local", "password": "ChangeMe123!"})
token = r.json().get("access_token", "")
h = {"Authorization": f"Bearer {token}"}
print(f"Login: {r.status_code}")

# Core endpoints
test("Health", requests.get, "/health")
test("Me", requests.get, "/auth/me", headers=h)
test("Projects", requests.get, "/projects", headers=h)
test("Vision", requests.get, "/bom2/vision", headers=h)
test("Requirements", requests.get, "/bom2/requirements", headers=h)
test("Providers", requests.get, "/ai/providers", headers=h)
test("Accounts", requests.get, "/ai/accounts", headers=h)
test("Pool Summary", requests.get, "/ai/pool-summary", headers=h)
test("Resources", requests.get, "/ai/resources", headers=h)
test("Skills", requests.get, "/skills", headers=h)
test("Skill Assignments", requests.get, "/skills/assignments", headers=h)
test("Deliberation List", requests.get, "/deliberation", headers=h)
test("Integration Services", requests.get, "/integration/services", headers=h)
test("Trace Matrix", requests.get, "/bom2/trace/matrix", headers=h)
test("Intake Sessions", requests.get, "/bom2/intake/sessions", headers=h)
test("PM Status", requests.get, "/bom2/integration/pm/status", headers=h)

print(f"\n{'='*40}")
print(f"Results: {ok} passed, {fail} failed, {ok+fail} total")
sys.exit(0 if fail == 0 else 1)
