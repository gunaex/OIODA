"""Seed skills into the Skill Registry."""
import requests, json

BASE = "http://127.0.0.1:8000/api"

r = requests.post(f"{BASE}/auth/login", json={"email": "admin@conductoragain.local", "password": "ChangeMe123!"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

skills = [
    ("vision-intake", "Vision Intake", "vision", "Extract objectives, constraints, and assumptions from a business vision statement."),
    ("domain-clarifier", "Domain Clarifier", "requirement", "Propose structured clarification questions for ambiguous domain requirements."),
    ("requirement-completeness", "Requirement Completeness Review", "review", "Identify missing, ambiguous, or conflicting information in requirements."),
    ("scope-decomposer", "Scope Decomposer", "planning", "Decompose high-level scope into workstreams, deliverables, and traceable units."),
    ("defect-triage", "Defect Triage", "analysis", "Analyze a defect: severity, affected artifacts, regression risk, and fix priority."),
    ("impact-analysis", "Impact Analysis", "analysis", "Cross-reference a change against requirements, PM features, and QA tests."),
    ("decision-brief", "Decision Brief", "decision", "Synthesize evidence, options, risks, and recommendations into a structured decision brief."),
    ("independent-critique", "Independent Critique", "review", "Blind peer review: critique another response using evidence and structured criteria."),
    ("decision-judge", "Decision Judge", "decision", "Evaluate anonymous candidates against a fixed rubric and produce a decision recommendation."),
]

for sid, name, cat, desc in skills:
    s = requests.post(f"{BASE}/skills", headers=h, json={
        "skill_id": sid,
        "name": name,
        "category": cat,
        "description": desc,
        "execution_targets": ["CONDUCTOR_SERVER"],
        "capability_requirements": {"capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT"], "minimumContextTokens": 16000},
        "model_policy": {"allowedProviderTypes": ["OFFICIAL_API", "LOCAL_MODEL"]},
        "data_policy": {"maximumClassification": "INTERNAL"},
        "approval_policy": {"resultType": "AI_RECOMMENDATION"},
        "budget_policy": {"maximumEstimatedCostUsd": 0.25},
    }).json()
    print(f"Skill: {s['name']} ({s['skill_id']})")

    v = requests.post(f"{BASE}/skills/{s['id']}/versions", headers=h, json={
        "skill_db_id": s["id"],
        "system_instructions": f"You are a {name} specialist. Provide structured, evidence-based analysis.",
        "prompt_template": "Analyze the following:\n\n{{input}}",
        "release_notes": "Initial draft",
    }).json()
    print(f"  v{v['version']} created")

    requests.post(f"{BASE}/skills/versions/{v['id']}/publish", headers=h)
    print(f"  v{v['version']} published")

print("\nDone! Seeded 9 skills with published versions.")
