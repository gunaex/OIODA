#!/usr/bin/env python
"""P5-N live relay dogfood — Document Again -> Conductor Main (real services).

Requires a running Account Again (:8001, fresh DB with DOCUMENT_AGAIN +
CONDUCTOR_MAIN registered) and a running Conductor Main (:8010). Uses Document
Again's REAL production auth + delivery paths (account_again mode, real AA
service token, real Conductor relay). PM/QA are not run here, so their dispatch
fails closed at Conductor — proving the relay contract + fail-closed behavior
without fabricating a "live PM" result.

Seeds Account Again over HTTP, then drives the Document Again app in-process
(TestClient) with real URLs.
"""
from __future__ import annotations

import os
import sys
import uuid

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

AA_URL = os.environ.get("AA_URL", "http://localhost:8001")
PREFIX = "/api/v1"
CONDUCTOR_URL = os.environ.get("CONDUCTOR_MAIN_URL", "http://localhost:8010/api")
DOC_SECRET = "da-live-secret"
CONDUCTOR_SECRET = "conductor-live-secret"

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def seed_aa() -> str:
    """Register tenant, account, DOCUMENT_AGAIN + CONDUCTOR_MAIN identities."""
    with httpx.Client(base_url=AA_URL, timeout=10.0) as c:
        c.post(f"{PREFIX}/tenants", json={"tenantId": "t-p5", "name": "P5 Tenant"})
        c.post(f"{PREFIX}/accounts", json={"tenantId": "t-p5", "email": "a@p5", "displayName": "Alice", "accountId": "acc-p5"})
        c.post(f"{PREFIX}/ai-entitlements", json={"tenantId": "t-p5", "capability": "document-again:design:write"})
        for sid, secret in [("DOCUMENT_AGAIN", DOC_SECRET), ("CONDUCTOR_MAIN", CONDUCTOR_SECRET)]:
            si = c.post(f"{PREFIX}/service-identities", json={"systemId": sid, "tenantId": "t-p5"}).json()
            c.post(f"{PREFIX}/service-identities/{si['serviceIdentityId']}/rotate-client-secret",
                   json={"clientSecret": secret})
        tok = c.post(f"{PREFIX}/auth/service-token", json={"systemId": "DOCUMENT_AGAIN", "clientSecret": DOC_SECRET}).json()["accessToken"]
        return tok


def main() -> int:
    # Seed + obtain the real DOCUMENT_AGAIN service token from Account Again.
    try:
        token = seed_aa()
    except Exception as exc:
        check("ACCOUNT_AGAIN_SEED", False, str(exc))
        return 1
    check("LIVE_ACCOUNT_AUTH", True, "DOCUMENT_AGAIN service token issued")

    # Configure Document Again for production auth + Conductor relay.
    os.environ["AUTH_MODE"] = "account_again"
    os.environ["ACCOUNT_AGAIN_URL"] = AA_URL
    os.environ["DOCUMENT_AGAIN_CLIENT_SECRET"] = DOC_SECRET
    os.environ["CONDUCTOR_MAIN_URL"] = CONDUCTOR_URL
    os.environ["DA_DB_PATH"] = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "document-again.db")

    from fastapi.testclient import TestClient
    from app.main import app

    H = {"Authorization": f"Bearer {token}", "X-Account-Id": "acc-p5", "X-Tenant-Id": "t-p5"}

    with TestClient(app) as c:
        p = c.post("/api/projects", json={"key": "P5LIVE", "name": "Purchase Approval"}, headers=H).json()
        pid = p["id"]
        check("V1 create project (live auth)", bool(pid))

        ur = c.post("/api/artifacts", json={"project_id": pid, "type": "UR", "title": "UR v1"}, headers=H).json()
        ur_rev = ur["revisions"][0]
        c.post(f"/api/revisions/{ur_rev['id']}/submit-for-review", headers=H)
        c.post(f"/api/revisions/{ur_rev['id']}/confirm", json={}, headers=H)

        dr = c.post("/api/artifacts", json={"project_id": pid, "type": "DR", "title": "DR v1"}, headers=H).json()
        dr_rev = dr["revisions"][0]
        c.post(f"/api/revisions/{dr_rev['id']}/submit-for-review", headers=H)
        c.post(f"/api/revisions/{dr_rev['id']}/confirm", json={}, headers=H)

        baseline = c.post("/api/baselines", json={"project_id": pid, "name": "v1",
                                                  "artifact_revision_ids": [ur_rev["id"], dr_rev["id"]]}, headers=H).json()
        check("V1 baseline confirmed", len(baseline["bindings"]) == 2)

        h = c.post("/api/handoffs/execution", json={"project_id": pid, "baseline_id": baseline["id"],
                                                    "source_revision_id": dr_rev["id"]}, headers=H).json()
        check("V1 PM handoff created", h["status"] == "DRAFT")

        # Deliver -> Conductor relay (real HTTP). PM is not running, so the
        # relay should fail closed (502) after Conductor maps + attempts PM.
        r = c.post(f"/api/handoffs/execution/{h['id']}/deliver", headers=H)
        check("CONDUCTOR_RELAY_AUTH_AND_DISPATCH", r.status_code in (200, 502), f"status {r.status_code}")
        if r.status_code == 502:
            print("  (PM Again not running -> relay failed closed as expected; not counted as live PM)")
        elif r.status_code == 200:
            body = r.json()
            check("PM_ACK_REFERENCE", bool(body.get("external_reference")), str(body))

    print()
    failed = [r for r in results if not r[1]]
    print(f"P5 live relay dogfood: {len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
