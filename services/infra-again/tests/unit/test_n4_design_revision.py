"""Phase N4.0 — Design revision lifecycle acceptance tests.

N3 found DesignBaseline.revision existed but nothing ever incremented it.
Fixed in flow/api.py: update-flow now bumps revision deterministically on
genuine execution-relevant content change, transitions an already-frozen
baseline to DESIGN_CHANGED_AFTER_ACCEPTANCE (previously-unused domain
state), and accept() now accepts that state back to BASELINE_FROZEN.
"""

from __future__ import annotations

from infra_again.flow.api import _apply_canonical_content, _compute_architecture_checksum
from infra_again.flow.models import DesignBaseline, DesignStatus


def _flow(*node_ids: str) -> dict:
    return {"nodes": [{"nodeId": n, "category": "STORAGE", "provider": "AWS", "nativeService": "s3"} for n in node_ids], "edges": []}


def test_checksum_deterministic_for_identical_content():
    f1 = _flow("N1", "N2")
    f2 = _flow("N2", "N1")  # different order, same content
    assert _compute_architecture_checksum(f1) == _compute_architecture_checksum(f2)


def test_checksum_ignores_presentation_only_fields():
    f1 = {"nodes": [{"nodeId": "N1", "category": "STORAGE", "provider": "AWS", "nativeService": "s3",
                      "name": "Bucket A", "position": {"x": 0, "y": 0}}], "edges": []}
    f2 = {"nodes": [{"nodeId": "N1", "category": "STORAGE", "provider": "AWS", "nativeService": "s3",
                      "name": "Renamed Bucket", "position": {"x": 500, "y": 300}}], "edges": []}
    assert _compute_architecture_checksum(f1) == _compute_architecture_checksum(f2)


def test_checksum_changes_on_real_content_change():
    f1 = _flow("N1")
    f2 = _flow("N1", "N2")
    assert _compute_architecture_checksum(f1) != _compute_architecture_checksum(f2)


def test_revision_bump_on_canonical_change():
    d = DesignBaseline()
    original_revision = d.revision
    changed = _apply_canonical_content(d, _flow("N1"))
    assert changed is True
    assert d.revision == original_revision + 1


def test_no_revision_bump_on_identical_resave():
    d = DesignBaseline()
    _apply_canonical_content(d, _flow("N1"))
    rev_after_first = d.revision
    changed = _apply_canonical_content(d, _flow("N1"))
    assert changed is False
    assert d.revision == rev_after_first


def test_design_id_preserved_across_revision_bumps():
    d = DesignBaseline()
    original_id = d.design_id
    _apply_canonical_content(d, _flow("N1"))
    _apply_canonical_content(d, _flow("N1", "N2"))
    assert d.design_id == original_id


def test_frozen_baseline_edit_transitions_to_changed_after_acceptance():
    d = DesignBaseline()
    _apply_canonical_content(d, _flow("N1"))
    d.accept("tester")
    assert d.status == DesignStatus.BASELINE_FROZEN
    rev_at_freeze = d.revision

    changed = _apply_canonical_content(d, _flow("N1", "N2"))
    assert changed is True
    assert d.revision == rev_at_freeze + 1
    assert d.status == DesignStatus.DESIGN_CHANGED_AFTER_ACCEPTANCE


def test_read_never_bumps_revision():
    d = DesignBaseline()
    _apply_canonical_content(d, _flow("N1"))
    rev = d.revision
    # Simulate N reads (to_dict is the read path — never touches revision)
    for _ in range(5):
        d.to_dict()
    assert d.revision == rev


# ═══════════════════════════════════════════════════════════════════
# Live API proof — full lifecycle through the real endpoints
# ═══════════════════════════════════════════════════════════════════


def test_live_update_flow_bumps_revision_and_reaccept_works():
    from fastapi.testclient import TestClient
    from infra_again.api import app
    client = TestClient(app)

    r = client.post("/api/v1/designs", params={"name": "N4 Rev API Test"})
    did = r.json()["design"]["designId"]

    nodes = [{"nodeId": "N1", "category": "STORAGE", "provider": "AWS", "nativeService": "s3"}]
    r = client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes, "edges": []}})
    assert r.json()["contentChanged"] is True
    rev_1 = r.json()["revision"]

    r = client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes, "edges": []}})
    assert r.json()["contentChanged"] is False
    assert r.json()["revision"] == rev_1

    r = client.post(f"/api/v1/designs/{did}/accept")
    assert r.json()["design"]["status"] == "BASELINE_FROZEN"

    nodes2 = nodes + [{"nodeId": "N2", "category": "DATABASE", "provider": "AWS", "nativeService": "rds"}]
    r = client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes2, "edges": []}})
    assert r.json()["designStatus"] == "DESIGN_CHANGED_AFTER_ACCEPTANCE"
    assert r.json()["revision"] == rev_1 + 1

    r = client.post(f"/api/v1/designs/{did}/accept")
    assert r.json()["design"]["status"] == "BASELINE_FROZEN"
    assert r.json()["design"]["revision"] == rev_1 + 1
