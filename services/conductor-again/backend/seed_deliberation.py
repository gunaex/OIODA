"""Seed a demo deliberation case with full flow."""
import requests

BASE = "http://127.0.0.1:8000/api"
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@conductoragain.local", "password": "ChangeMe123!"})
if r.status_code != 200:
    print(f"Login failed: {r.status_code} {r.text}")
    exit(1)
token = r.json().get("access_token")
if not token:
    print(f"No token in response: {r.json()}")
    exit(1)
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Create deliberation
resp = requests.post(f"{BASE}/deliberation/start", headers=h, json={
    "title": "Should BOM circular-reference validation prevent only direct self-reference, or all transitive cycles?",
    "trigger": "HIGH_IMPACT",
    "project_slug": "bom-system",
    "task": "A Production BOM allows items to reference sub-components. Should the system: A) Prevent only direct self-reference, B) Allow draft cycles but block publish, or C) Reject all cycles immediately?",
    "criteria": "Data integrity, UX for draft workflows, performance at scale, backward compatibility.",
    "skill_id": "decision-brief",
    "min_members": 2,
})
print(f"Start status: {resp.status_code}")
if resp.status_code != 200:
    print(f"Error: {resp.text}")
    exit(1)
case = resp.json()
cid = case["case_id"]
print(f"Panel: {case['panel_size']} members, case_id={cid[:8]}...")
for m in case["members"]:
    print(f"  {m['label']}: {m['role']} ({m['provider']} / {m['model']})")

# Submit independent answers
answers = [
    {"conclusion": "Option A: Prevent direct self-reference only. Transitive cycles are rare and full graph traversal on every save hurts performance.",
     "recommended_action": "Implement direct-cycle check on save. Add transitive scanner as admin job.",
     "confidence": 0.85, "evidence_quality": 0.9},
    {"conclusion": "Option C: Reject ALL cycles immediately. Allowing any circular reference introduces data integrity risk.",
     "recommended_action": "Implement full DFS cycle detection on save. Run one-time cleanup for existing data.",
     "confidence": 0.92, "evidence_quality": 0.85},
]
for i, m in enumerate(case["members"]):
    ans = answers[i]
    requests.post(f"{BASE}/deliberation/{cid}/submit", headers=h, json={"member_id": m["id"], **ans})
    print(f"  {m['label']} submitted (conf: {ans['confidence']})")

# Critiques
subs_resp = requests.get(f"{BASE}/deliberation/{cid}", headers=h)
subs = subs_resp.json()["submissions"]
for i, m in enumerate(case["members"]):
    for j, s in enumerate(subs):
        if s["member_id"] != m["id"]:
            requests.post(f"{BASE}/deliberation/{cid}/critique", headers=h, json={
                "reviewer_member_id": m["id"],
                "target_submission_id": s["id"],
                "target_label": f"Candidate {chr(65 + j)}",
                "strengths": ["Clear reasoning", "Good evidence"],
                "weaknesses": ["Could consider edge cases"],
                "overall_assessment": "Well-structured with valid points.",
            })
            break
print("Critiques submitted")

# Dissent from Candidate B (minority)
mc = case["members"][1]
requests.post(f"{BASE}/deliberation/{cid}/dissent", headers=h, json={
    "member_id": mc["id"],
    "position": "Option B should not be dismissed. Manufacturing industry allows draft flexibility. Strict creation-time enforcement frustrates users.",
    "supporting_evidence": ["SAP/Oracle allow draft BOM cycles", "40% of BOM edits happen in draft mode"],
    "rejected_majority_assumptions": ["Transitive cycles are not as rare as assumed"],
    "risk_if_minority_correct": "User backlash and support ticket wave within first week.",
    "suggested_verification": "Run 2-week A/B test before full rollout.",
})
print("Dissent recorded from Candidate C")

# Decide
requests.post(f"{BASE}/deliberation/{cid}/decide", headers=h, json={
    "outcome": "SUPPORTED_MAJORITY_WITH_DISSENT",
    "final_decision": "Implement Option A now. Schedule Option C for Phase 2. Acknowledge Candidate C's dissent — evaluate via A/B test.",
    "human_approved": True,
    "human_approved_by": "Conductor Admin",
})
print("Decision: SUPPORTED_MAJORITY_WITH_DISSENT")
print(f"\nDone! Browse to /bom-system/deliberation to view.")
