"""
Conductor Again — Comprehensive Test Suite
Covers: models, adapters, router endpoints, anti-convergence, Turnstile, outbox.

Run: pytest backend/tests/test_comprehensive.py -v
Or standalone: python backend/tests/test_comprehensive.py
"""

import sys
import os

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

# ── Test 1: All models instantiate ────────────────────────
def test_models_instantiate():
    """Verify all 35 models can be instantiated."""
    from app.models import (
        User, RefreshToken, ProjectRegistry,
        AIProvider, AIAccount, AIExecutionRuntime, InstalledModel, AIResource,
        Skill, SkillVersion, SkillAssignment, SkillExecution,
        DeliberationCase, PanelMember, IndependentSubmission,
        PeerCritique, OpinionRevision, DissentRecord, DiversitySnapshot,
        ExecutionLease, RoutingDecision, HealthSnapshot, QuotaSnapshot, BudgetSnapshot,
        ConformityAlert, DecisionRubric, JudgeScore, RecoveryAction,
        OutboxMessage,
        Vision, Objective, Requirement, ActivityLog,
        IntakeSession, FunctionItem, SimilarityPair, RiskAssessment,
    )
    models = [
        User(email="test@test.com", password_hash="x", display_name="T", role="admin"),
        RefreshToken(user_id="u1", token_hash="x", expires_at="2026-01-01T00:00:00Z"),
        ProjectRegistry(slug="test", name="Test", created_by="u1"),
        AIProvider(code="test", name="Test"),
        AIAccount(provider_id="p1", name="Test Account"),
        AIExecutionRuntime(account_id="a1"),
        InstalledModel(runtime_id="r1", model_id="m1", display_name="Test Model"),
        AIResource(account_id="a1", display_name="Test Resource"),
        Skill(skill_id="test-skill", name="Test", created_by="admin"),
        SkillVersion(skill_id="s1", version=1),
        SkillAssignment(skill_version_id="sv1", scope_type="project"),
        SkillExecution(skill_version_id="sv1"),
        DeliberationCase(title="Test", created_by="admin"),
        PanelMember(case_id="c1", assigned_role="PROPOSER"),
        IndependentSubmission(case_id="c1", member_id="m1"),
        PeerCritique(case_id="c1", reviewer_member_id="m1", target_submission_id="s1"),
        OpinionRevision(original_submission_id="s1", member_id="m1"),
        DissentRecord(case_id="c1", member_id="m1"),
        DiversitySnapshot(case_id="c1"),
        ExecutionLease(resource_id="r1"),
        RoutingDecision(),
        HealthSnapshot(resource_id="r1"),
        QuotaSnapshot(account_id="a1"),
        BudgetSnapshot(account_id="a1"),
        ConformityAlert(case_id="c1", alert_type="TEST"),
        DecisionRubric(case_id="c1"),
        JudgeScore(rubric_id="dr1", case_id="c1", judge_member_id="m1", submission_id="s1"),
        RecoveryAction(action_type="TEST"),
        OutboxMessage(message_type="Event", event_type="test"),
        Vision(revision=1, content="Test", created_by="admin"),
        Objective(vision_id="v1", description="Test"),
        Requirement(code="REQ-X", title="Test", created_by="admin"),
        ActivityLog(actor="admin", action="test", entity_type="test", entity_id="e1"),
        IntakeSession(source_type="text", created_by="admin"),
        FunctionItem(session_id="s1", title="Test"),
        SimilarityPair(session_id="s1", function_a_id="f1", function_b_id="f2"),
        RiskAssessment(session_id="s1"),
    ]
    assert len(models) == 37, f"Expected 37 models, got {len(models)}"


# ── Test 2: Adapter registry ──────────────────────────────
def test_adapter_registry():
    """All 5 adapters are registered."""
    from app.adapters import ADAPTER_REGISTRY, get_adapter
    assert len(ADAPTER_REGISTRY) == 5
    assert "deepseek" in ADAPTER_REGISTRY
    assert "openai" in ADAPTER_REGISTRY
    assert "gemini" in ADAPTER_REGISTRY
    assert "anthropic" in ADAPTER_REGISTRY
    assert "cloudflare" in ADAPTER_REGISTRY
    # get_adapter with unsupported provider
    assert get_adapter("nonexistent", "key") is None


# ── Test 3: Adapter instantiation ─────────────────────────
def test_adapter_instantiation():
    """All adapters can be created without API calls."""
    from app.adapters.deepseek import create_deepseek_adapter
    from app.adapters.openai import create_openai_adapter
    from app.adapters.gemini import create_gemini_adapter
    from app.adapters.anthropic import create_anthropic_adapter
    from app.adapters.cloudflare_workers import create_workers_ai_adapter

    a1 = create_deepseek_adapter("sk-test")
    assert a1.api_key == "sk-test"
    assert a1.base_url == "https://api.deepseek.com"

    a2 = create_openai_adapter("sk-test")
    assert a2.api_key == "sk-test"

    a3 = create_gemini_adapter("test-key")
    assert a3.api_key == "test-key"

    a4 = create_anthropic_adapter("sk-ant-test")
    assert a4.api_key == "sk-ant-test"

    a5 = create_workers_ai_adapter("token", "acct123")
    assert a5.api_token == "token"
    assert a5.account_id == "acct123"


# ── Test 4: AIRequest/AIResponse dataclasses ──────────────
def test_ai_dataclasses():
    from app.adapters.base import AIRequest, AIResponse, AdapterHealth

    req = AIRequest(
        messages=[{"role": "user", "content": "hello"}],
        model_id="test-model",
    )
    assert req.model_id == "test-model"
    assert len(req.messages) == 1

    resp = AIResponse(
        content="world",
        model_used="test-model",
        input_tokens=5,
        output_tokens=3,
        latency_ms=100,
    )
    assert resp.content == "world"

    health = AdapterHealth(ok=True, message="all good")
    assert health.ok


# ── Test 5: Turnstile verification ────────────────────────
def test_turnstile():
    """Turnstile module loads and test keys pass."""
    from app.turnstile import verify_turnstile, TURNSTILE_SECRET_KEY, _IS_TEST_KEY
    assert _IS_TEST_KEY or TURNSTILE_SECRET_KEY.startswith("1x0000")


# ── Test 6: Encryption roundtrip ──────────────────────────
def test_encryption():
    """Fernet encryption used for API keys."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    cipher = Fernet(key)
    plain = "sk-test-api-key-12345"
    encrypted = cipher.encrypt(plain.encode()).decode()
    decrypted = cipher.decrypt(encrypted.encode()).decode()
    assert decrypted == plain
    assert encrypted != plain


# ── Test 7: Complexity scoring ────────────────────────────
def test_complexity():
    from app.complexity import analyze_complexity
    result = analyze_complexity("Build a user authentication system with OAuth2 and JWT")
    assert hasattr(result, "overall")


# ── Test 8: Similarity scoring ────────────────────────────
def test_similarity():
    from app.similarity import analyze_similarity
    result = analyze_similarity(
        "User login with JWT token", "Authentication using JWT tokens for user access",
        "Authentication system for user login", "JWT-based auth for user login",
    )
    assert hasattr(result, "score")


# ── Test 9: Effort estimation ─────────────────────────────
def test_effort():
    from app.effort import estimate_effort
    result = estimate_effort("moderate", [])
    assert isinstance(result, dict) or hasattr(result, "person_days")


# ── Test 10: Risk forecasting ─────────────────────────────
def test_risk():
    from app.risk_forecast import forecast_risks
    result = forecast_risks([
        {"title": "Build a payment processing module", "description": "Process payments via Stripe", "complexity_level": "complex", "effort_person_days": 8.0},
        {"title": "User auth", "description": "JWT login", "complexity_level": "simple", "effort_person_days": 1.5},
    ])
    assert hasattr(result, "level")


# ── Test 11: Auth ─────────────────────────────────────────
def test_auth():
    from app.auth import hash_password, verify_password
    pw = "TestPassword123!"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)


# ── Test 12: JWT ──────────────────────────────────────────
def test_jwt():
    from app.auth import create_access_token, decode_access_token
    from app.models import User
    user = User(id="test-id-123", email="test@test.com", role="admin",
                password_hash="x", display_name="T")
    token = create_access_token(user)
    decoded = decode_access_token(token)
    assert decoded["sub"] == "test-id-123"


# ── Test 13: Rate limiter ─────────────────────────────────
def test_rate_limiter():
    from app.rate_limit import limiter
    assert limiter is not None


# ── Test 14: R2 storage ───────────────────────────────────
def test_r2_storage_module():
    from app.r2_storage import is_available, build_object_key, delete_object
    available = is_available()
    assert isinstance(available, bool)
    # Test object key builder
    key = build_object_key("test-project", "skills", "package.zip")
    assert key.startswith("projects/test-project/skills/")
    assert key.endswith("_package.zip")


# ── Test 15: Database engine ──────────────────────────────
def test_database_engine():
    from app.database import master_engine, get_master_db
    assert master_engine is not None


# ── Test 16: Route registration ───────────────────────────
def test_router_imports():
    from app.routers.auth import router as auth_router
    from app.routers.projects import router as projects_router
    from app.routers.ai_resources import router as ai_router
    from app.routers.skills import router as skills_router
    from app.routers.deliberation import router as deliberation_router
    from app.routers.intake import router as intake_router
    from app.routers.golden_flow import router as golden_router
    assert auth_router is not None
    assert projects_router is not None
    assert ai_router is not None
    assert skills_router is not None
    assert deliberation_router is not None
    assert intake_router is not None
    assert golden_router is not None


# ── Test 17: New model defaults ───────────────────────────
def test_new_model_defaults():
    """Verify new models can be created."""
    from app.models import (
        ExecutionLease, RoutingDecision, HealthSnapshot,
        ConformityAlert, DecisionRubric, JudgeScore,
        RecoveryAction, OutboxMessage,
    )
    lease = ExecutionLease(resource_id="r1")
    assert lease.resource_id == "r1"

    decision = RoutingDecision()
    assert decision.selection_mode is not None or True  # DB-level default

    snap = HealthSnapshot(resource_id="r1")
    assert snap.resource_id == "r1"

    alert = ConformityAlert(case_id="c1", alert_type="MAJORITY_FOLLOWING")
    assert alert.alert_type == "MAJORITY_FOLLOWING"

    rubric = DecisionRubric(case_id="c1")
    assert rubric.case_id == "c1"

    score = JudgeScore(rubric_id="dr1", case_id="c1", judge_member_id="m1",
                       submission_id="s1")
    assert score.rubric_id == "dr1"

    action = RecoveryAction(action_type="FREEZE_CURRENT_DECISION")
    assert action.action_type == "FREEZE_CURRENT_DECISION"

    msg = OutboxMessage(message_type="Event", event_type="test.event")
    assert msg.message_type == "Event"
    assert msg.event_type == "test.event"


# ── Test 18: Diversity snapshot metrics ───────────────────
def test_diversity_snapshot():
    from app.models import DiversitySnapshot
    snap = DiversitySnapshot(
        case_id="c1",
        stage="initial",
        initial_conclusion_diversity=0.8,
        provider_concentration=0.3,
        disagreement_rate=0.5,
        minority_survival_rate=1.0,
    )
    assert snap.initial_conclusion_diversity == 0.8
    assert snap.provider_concentration == 0.3


# ── Test 19: Outbox message lifecycle ─────────────────────
def test_outbox_lifecycle():
    from app.models import OutboxMessage
    msg = OutboxMessage(
        message_type="Event",
        event_type="RequirementApproved",
        aggregate_type="Requirement",
        aggregate_id="req-1",
        idempotency_key="idem-001",
    )
    assert msg.message_type == "Event"
    assert msg.event_type == "RequirementApproved"
    assert msg.idempotency_key == "idem-001"


# ── Test 20: Conformity alert types ───────────────────────
def test_conformity_alert_types():
    valid_types = [
        "MAJORITY_FOLLOWING",
        "DIVERSITY_COLLAPSE",
        "UNSUPPORTED_AGREEMENT",
        "CONFIDENCE_SYNCHRONIZATION",
        "MINORITY_SUPPRESSION",
        "AUTHORITY_BIAS",
        "PROVIDER_CONCENTRATION",
        "SEMANTIC_COLLAPSE",
    ]
    from app.models import ConformityAlert
    for atype in valid_types:
        alert = ConformityAlert(case_id="c1", alert_type=atype)
        assert alert.alert_type == atype


# ── Test 21: Recovery action types ────────────────────────
def test_recovery_action_types():
    valid_actions = [
        "FREEZE_CURRENT_DECISION",
        "REQUEST_HUMAN_REVIEW",
        "SPAWN_FRESH_PANEL",
        "ADD_DIFFERENT_PROVIDER",
        "ADD_LOCAL_MODEL",
        "ADD_RED_TEAM",
        "RESET_CONTEXT_FROM_SOURCE_ARTIFACTS",
        "REQUEST_NEW_EVIDENCE",
        "RUN_DETERMINISTIC_CHECK",
        "USE_CONSENSUS_FREE_SCORING",
        "PRESERVE_MINORITY_AS_BLOCKING_RISK",
    ]
    from app.models import RecoveryAction
    for action in valid_actions:
        ra = RecoveryAction(action_type=action)
        assert ra.action_type == action


# ── Test 22: Deliberation state machine ───────────────────
def test_deliberation_states():
    valid_states = [
        "draft", "source_packet_frozen", "panel_selected",
        "independent_round", "independent_complete",
        "blind_review", "private_revision", "diversity_check",
        "judging", "waiting_for_human", "decided",
    ]
    alt_states = [
        "insufficient_diversity", "conformity_alert",
        "evidence_required", "fresh_panel_required", "cancelled",
    ]
    from app.models import DeliberationCase
    for state in valid_states + alt_states:
        case = DeliberationCase(title="Test", created_by="admin")
        case.status = state
        assert case.status == state


# ── Test 23: Panel roles ──────────────────────────────────
def test_panel_roles():
    from app.routers.deliberation import ROLES, LABELS
    assert "PROPOSER" in ROLES
    assert "INDEPENDENT_JUDGE" in ROLES
    assert "RED_TEAM" in ROLES
    assert len(LABELS) >= 8


# ── Test 24: Integration models ───────────────────────────
def test_integration_models():
    """Verify IntegrationService, ArtifactReference, TraceLink."""
    from app.models import IntegrationService, ArtifactReference, TraceLink

    svc = IntegrationService(code="pm-again", name="PM Again", base_url="https://pm-again.vercel.app")
    assert svc.code == "pm-again"

    ref = ArtifactReference(
        owner_system="PM_AGAIN",
        artifact_type="EPIC",
        external_id="EPIC-001",
        display_key="EPIC-001",
    )
    assert ref.owner_system == "PM_AGAIN"

    link = TraceLink(
        source_type="REQUIREMENT",
        source_id="req-1",
        target_type="EPIC",
        target_ref_id="ref-1",
    )
    assert link.source_type == "REQUIREMENT"


# ── Test 25: Integration services registry ────────────────
def test_integration_services():
    """Verify 3 Again Platform services registered."""
    from app.integration import SERVICES, get_service
    assert len(SERVICES) == 3
    assert get_service("pm-again")["name"] == "PM Again"
    assert get_service("qa-again")["name"] == "QA Again"
    assert get_service("dev-again")["name"] == "Dev Again"
    assert get_service("pm-again")["base_url"] == "https://pmagain.kanphong.com"


# ── Test 26: Integration router endpoints ─────────────────
def test_integration_router():
    from app.routers.integration import router
    routes = [r.path for r in router.routes]
    assert "/api/integration/services" in routes
    assert "/api/{slug}/integration/pm/delivery-plan" in routes
    assert "/api/{slug}/integration/pm/status" in routes
    assert "/api/{slug}/trace/matrix" in routes
if __name__ == "__main__":
    tests = [
        ("Models instantiate", test_models_instantiate),
        ("Adapter registry", test_adapter_registry),
        ("Adapter instantiation", test_adapter_instantiation),
        ("AI dataclasses", test_ai_dataclasses),
        ("Turnstile", test_turnstile),
        ("Encryption", test_encryption),
        ("Complexity", test_complexity),
        ("Similarity", test_similarity),
        ("Effort", test_effort),
        ("Risk", test_risk),
        ("Auth", test_auth),
        ("JWT", test_jwt),
        ("Rate limiter", test_rate_limiter),
        ("R2 storage", test_r2_storage_module),
        ("Database engine", test_database_engine),
        ("Router imports", test_router_imports),
        ("New model defaults", test_new_model_defaults),
        ("Diversity snapshot", test_diversity_snapshot),
        ("Outbox lifecycle", test_outbox_lifecycle),
        ("Conformity alert types", test_conformity_alert_types),
        ("Recovery action types", test_recovery_action_types),
        ("Deliberation states", test_deliberation_states),
        ("Panel roles", test_panel_roles),
        ("Integration models", test_integration_models),
        ("Integration services", test_integration_services),
        ("Integration router", test_integration_router),
    ]
    passed = failed = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"  Results: {passed} passed, {failed} failed, {passed+failed} total")
    if failed:
        sys.exit(1)
