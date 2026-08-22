import json

from app import resolution_intelligence as intelligence


def center_for(state="WAITING_ON_OWNER", reason="QA evidence is not present.", *,
               failure_category=None, with_route=True, history=None):
    resolution = {
        "resolution_id": "r1", "project_id": "p1", "impact_candidate_id": "i1",
        "confirmation_id": "c1", "resolution_state": state,
        "resolution_reason": reason, "evaluation_rule_id": "QA-VALIDATION-EVIDENCE-COMPLETE",
        "evaluation_rule_version": "1", "state_entered_at": "2026-08-22T00:00:00+00:00",
        "history": history or [], "evidence_refs": ["truth-1"],
    }
    route = {
        "action_route_id": "a1", "confirmation_id": "c1",
        "action_type": "ROUTE_QA_VALIDATION_HANDOFF", "failure_category": failure_category,
        "status": "FAILED" if failure_category else "SUCCEEDED",
    }
    return {
        "project": {"id": "p1"},
        "resolution_summary": {"active": [resolution]},
        "action_summary": {"routes": [route] if with_route else []},
    }


def test_waiting_is_not_blocked_and_explains_required_truth():
    out = intelligence.analyze(center_for())
    item = out["unresolved_items"][0]
    assert item["state"] == "WAITING_ON_OWNER"
    assert item["reason_class"] == "MISSING_EVIDENCE"
    assert out["blocked"] == [] and out["waiting"] == [item]
    assert "QA source OK" in item["what_would_resolve_this"]
    assert item["safe_next_steps"][0]["action_type"] == "RECHECK"
    assert item["customer_acceptance"] is False and item["autonomous"] is False


def test_blocked_binding_and_recheck_are_distinct_priority_tiers():
    blocked = intelligence.analyze(center_for("BLOCKED", "Workspace binding is missing."))
    assert blocked["blocked"][0]["reason_class"] == "MISSING_BINDING"
    assert blocked["blocked"][0]["priority_tier"] == "P1"
    recheck = intelligence.analyze(center_for("RECHECK_REQUIRED", "Owner truth may have changed."))
    assert recheck["recheck_required"][0]["reason_class"] == "STALE_EVIDENCE"
    assert recheck["recheck_required"][0]["priority_tier"] == "P2"


def test_owner_unavailable_and_authorization_are_explicit():
    unavailable = intelligence.analyze(center_for("BLOCKED", "Owner unavailable.", failure_category="OWNER_UNAVAILABLE"))
    unauthorized = intelligence.analyze(center_for("BLOCKED", "Owner rejected request.", failure_category="UNAUTHORIZED"))
    assert unavailable["unresolved_items"][0]["reason_class"] == "OWNER_UNAVAILABLE"
    assert unauthorized["unresolved_items"][0]["reason_class"] == "AUTHORIZATION_REQUIRED"


def test_reopened_and_time_in_state_do_not_create_an_opaque_score():
    out = intelligence.analyze(center_for(history=[
        {"event_type": "IMPACT_RESOLUTION_RESOLVED"},
        {"event_type": "IMPACT_RESOLUTION_REOPENED"},
    ]))
    item = out["unresolved_items"][0]
    assert item["reopened"] is True and item["priority_tier"] == "P1"
    assert item["time_in_state_seconds"] >= 0
    assert "score" not in item and "score" not in out


def test_partial_packet_and_no_route_use_supported_fallbacks():
    out = intelligence.analyze(center_for("OPEN", "Impact needs action.", with_route=False))
    item = out["unresolved_items"][0]
    assert item["reason_class"] == "ACTION_REQUIRED"
    assert item["safe_next_steps"] == []
    assert item["action_readiness"] == "ACTION_NOT_SUPPORTED"
    assert out["performance"]["extra_owner_calls"] == 0


def test_ai_validator_rejects_false_authority_and_unknown_actions():
    packet = intelligence.analyze(center_for())
    evidence = packet["unresolved_items"][0]["evidence_ids"][0]
    raw = {"explanations": [
        {"resolution_id": "r1", "explanation": "This is resolved.", "evidence_ids": [evidence]},
        {"resolution_id": "r1", "explanation": "Customer accepted it.", "evidence_ids": [evidence]},
        {"resolution_id": "r1", "explanation": "Do the next thing.", "evidence_ids": [evidence], "action_type": "DEPLOY"},
        {"resolution_id": "r1", "explanation": "QA evidence remains missing.", "evidence_ids": [evidence], "action_type": "RECHECK"},
    ]}
    out = intelligence.validate_ai(raw, packet)
    assert len(out["explanations"]) == 1 and out["explanations"][0]["executable"] is False
    assert {x["reason"] for x in out["rejected_claims"]} == {
        "FALSE_RESOLUTION", "CUSTOMER_ACCEPTANCE_UNSUPPORTED", "UNKNOWN_ACTION"
    }


def test_assistant_falls_back_to_deterministic_packet(monkeypatch):
    packet = intelligence.analyze(center_for())
    monkeypatch.setattr(intelligence.reviewer, "_provider", lambda: None)
    out = intelligence.assistant(packet)
    assert out["status"] == "NOT_CONFIGURED"
    assert out["focus_items"] == packet["focus_items"]
    assert out["ai_authority"] == "NONE" and out["auto_execution"] is False


def test_assistant_accepts_only_cited_allowlisted_advice(monkeypatch):
    packet = intelligence.analyze(center_for())
    evidence = packet["unresolved_items"][0]["evidence_ids"][0]
    monkeypatch.setattr(intelligence.reviewer, "_provider", lambda: {
        "provider_id": "local", "model": "test", "supports_json_mode": True})
    class Provider:
        def generate_grounded_review(self, _system, _payload):
            return json.dumps({"explanations": [{"resolution_id": "r1",
                "explanation": "QA evidence remains missing.", "evidence_ids": [evidence],
                "action_type": "RECHECK"}]})
    out = intelligence.assistant(packet, provider_factory=lambda _: Provider())
    assert out["status"] == "AVAILABLE" and len(out["explanations"]) == 1
    assert out["explanations"][0]["executable"] is False
    assert out["evidence_citations"] == [evidence]
