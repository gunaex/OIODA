#!/usr/bin/env python
"""P4 failure dogfood — controlled outages and replay safety.

Exercises the failure invariants without any live downstream service:
Account outage fail-closed, PM/QA delivery outage, duplicate delivery,
worker restart, and baseline non-corruption under failure.

Run against a fresh, migrated database.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app import models as m
from app import services as svc
from app.account_client import AccountAgainClient, AccountAgainError
from app.db import Base

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def main() -> int:
    engine = create_engine("sqlite:///./data/document-again.db", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("pragma foreign_keys=ON")

    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    # 1. Account outage fail-closed (no downgrade)
    import httpx

    def down(request: httpx.Request):
        raise httpx.ConnectError("down", request=request)

    c = AccountAgainClient("http://aa", transport=httpx.MockTransport(down))
    try:
        c.validate_actor("tok", "acc-1", "t-1")
        check("ACCOUNT_OUTAGE_SAFE", False, "did not fail closed")
    except AccountAgainError as exc:
        check("ACCOUNT_OUTAGE_SAFE", exc.status_code == 503)

    # 2. PM delivery outage -> outbox FAILED, durable, no corruption
    project = svc.create_project(db, key="FAILQ", name="Failure Dogfood")
    svc.emit_event(db, event_type="EXECUTION_REQUESTED", project_id=project.id,
                   payload={"baselineId": "b1"}, target_services=["pm-again"], correlation_id="corr-f")

    def boom(o):
        raise RuntimeError("pm down")

    svc.deliver_due_events(db, boom)
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    check("PM_OUTAGE_SAFE", out.status == "FAILED" and out.attempt_count == 1)
    ev = db.execute(select(m.EcosystemEvent)).scalars().one()
    check("NO_LOST_DURABLE_EVENT", ev.payload == {"baselineId": "b1"})

    # 3. Duplicate delivery safe (idempotent)
    out.next_attempt_at = m.utcnow() - __import__("datetime").timedelta(seconds=10)
    db.commit()
    delivered = []
    svc.deliver_due_events(db, lambda o: delivered.append(o.id) or "ref-1")
    svc.deliver_due_events(db, lambda o: delivered.append(o.id) or "ref-1")
    check("DUPLICATE_DELIVERY_SAFE", len(delivered) == 1)

    # 4. Worker restart safe (SENT rows not re-delivered on a fresh pass)
    r = svc.deliver_due_events(db, lambda o: delivered.append(o.id) or "ref-2")
    check("WORKER_RESTART_SAFE", r == {"delivered": 0, "failed": 0})

    # 5. No baseline corruption under failure
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.UR, title="UR")
    rev = db.execute(select(m.ArtifactRevision).where(
        m.ArtifactRevision.artifact_id == art.id)).scalars().one()
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id)
    baseline = svc.create_baseline(db, project_id=project.id, name="B", artifact_revision_ids=[rev.id])
    binding = db.execute(select(m.BaselineBinding).where(
        m.BaselineBinding.baseline_id == baseline.id)).scalars().one()
    check("NO_BASELINE_CORRUPTION", binding.artifact_revision_id == rev.id)

    db.close()
    print()
    failed = [r for r in results if not r[1]]
    print(f"P4 failure dogfood: {len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
