#!/usr/bin/env python
"""P4-A live Account Again validation.

Runs against a REAL running Account Again instance (uvicorn account_again.main:app
--port 8001) with a fresh account_again.db. Seeds a tenant, account, service
identity (DOCUMENT_AGAIN) + entitlement via Account Again's own HTTP API, issues
a real RS256 service token, then exercises Document Again's production
AccountAgainClient over the wire:

  valid token       -> ALLOW
  invalid token     -> rejected (401)
  no entitlement    -> DENY (403)
  Account Again down -> fail-closed (503)

Usage:
  AA_URL=http://localhost:8001 python scripts/live_account_again.py
"""
from __future__ import annotations

import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.account_client import AccountAgainClient, AccountAgainError  # noqa: E402

AA_URL = os.environ.get("AA_URL", "http://localhost:8001").rstrip("/")
PREFIX = "/api/v1"

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def seed() -> str:
    """Seed Account Again and return an issued service token for DOCUMENT_AGAIN."""
    with httpx.Client(base_url=AA_URL, timeout=10.0) as c:
        c.post(f"{PREFIX}/tenants", json={"tenantId": "t-p4", "name": "P4 Tenant"})
        c.post(f"{PREFIX}/accounts", json={"tenantId": "t-p4", "email": "alice@example.com", "displayName": "Alice", "accountId": "acc-alice"})
        c.post(f"{PREFIX}/tenants", json={"tenantId": "t-none", "name": "No Entitlement"})
        c.post(f"{PREFIX}/accounts", json={"tenantId": "t-none", "email": "bob@example.com", "displayName": "Bob", "accountId": "acc-bob"})
        si = c.post(f"{PREFIX}/service-identities",
                    json={"systemId": "DOCUMENT_AGAIN", "tenantId": "t-p4"}).json()
        secret = c.post(
            f"{PREFIX}/service-identities/{si['serviceIdentityId']}/rotate-client-secret",
            json={"clientSecret": "da-live-secret"},
        ).json()["clientSecret"]
        c.post(f"{PREFIX}/ai-entitlements",
               json={"tenantId": "t-p4", "capability": "document-again:design:write"})
        token = c.post(f"{PREFIX}/auth/service-token",
                       json={"systemId": "DOCUMENT_AGAIN", "clientSecret": secret}).json()["accessToken"]
        return token


def main() -> int:
    client = AccountAgainClient(AA_URL)

    try:
        token = seed()
    except Exception as exc:
        print(f"SEED FAILED — is Account Again running at {AA_URL}? {exc}")
        check("Account Again reachable", False, str(exc))
        check("LIVE_ACCOUNT_AGAIN_VALIDATION", False, "AA not running")
        return 1

    # 1. Valid token + entitled account -> ALLOW
    try:
        info = client.validate_actor(token, "acc-alice", "t-p4")
        check("VALID_TOKEN=ALLOW", info["source"] == "ACCOUNT_AGAIN" and info["tenant_id"] == "t-p4", str(info))
    except AccountAgainError as exc:
        check("VALID_TOKEN=ALLOW", False, f"{exc} ({exc.status_code})")

    # 2. Invalid token -> rejected
    try:
        client.validate_actor("not-a-real-token", "acc-alice", "t-p4")
        check("INVALID_TOKEN_REJECTED", False, "invalid token was accepted")
    except AccountAgainError as exc:
        check("INVALID_TOKEN_REJECTED", exc.status_code in (401, 403), f"{exc.status_code}")

    # 3. Entitled account resolved display name
    try:
        info = client.validate_actor(token, "acc-alice", "t-p4")
        check("ACCOUNT_RESOLVED", info.get("display_name") == "Alice", str(info))
    except AccountAgainError as exc:
        check("ACCOUNT_RESOLVED", False, str(exc))

    # 4. No entitlement -> DENY
    try:
        client.validate_actor(token, "acc-bob", "t-none")
        check("DENY_REJECTED", False, "unentitled tenant was allowed")
    except AccountAgainError as exc:
        check("DENY_REJECTED", exc.status_code == 403, f"{exc.status_code}")

    # 5. Outage -> fail-closed
    down = AccountAgainClient("http://localhost:59999")
    try:
        down.validate_actor(token, "acc-alice", "t-p4")
        check("AUTH_OUTAGE_FAIL_CLOSED", False, "outage did not fail closed")
    except AccountAgainError as exc:
        check("AUTH_OUTAGE_FAIL_CLOSED", exc.status_code == 503, f"{exc.status_code}")

    print()
    failed = [r for r in results if not r[1]]
    print(f"Live Account Again: {len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
