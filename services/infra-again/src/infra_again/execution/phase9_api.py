"""Phase 9.2.1-9.5 Promotion + Rollback + UAT + Production Readiness API.

Authoritative persistence-backed control plane.
PERSISTED_STATE > PROCESS_MEMORY for all sensitive operations (9.2.1-B).
"""

from __future__ import annotations

import hashlib, json, os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from .phase9_models import (
    PromotionPackage, EnvironmentTarget, EnvironmentClassification,
    PromotionStatus, BlastRadius, validate_transition,
    create_sandbox_environment, create_controlled_real_target,
)
from . import phase9_persistence as persist
from . import persistence as exec_persist


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


# In-memory caches (NOT authoritative — persistence is source of truth)
_environments: dict[str, EnvironmentTarget] = {}
# Execution persistence instance for authoritative plan/package reload
_exec_db = exec_persist.ExecutionPersistence()


# ══════════════════════════════════════════════════════════
# 9.2.1-D: Authoritative plan/package reload
# ══════════════════════════════════════════════════════════

def _reload_plan(promo: dict) -> dict | None:
    """Reload ImplementationPlan from execution persistence."""
    plan_id = promo.get("implementationPlanId", "")
    if not plan_id:
        return None
    pkg_id = promo.get("executionPackageId", "")
    if pkg_id:
        pkg = _exec_db.load_package(pkg_id)
        if pkg:
            return {
                "planId": pkg.get("planId", plan_id),
                "planChecksum": pkg.get("planChecksum", ""),
                "packageId": pkg_id,
                "packageChecksum": pkg.get("packageChecksum", promo.get("packageChecksum", "")),
                "status": pkg.get("status", ""),
            }
    return {"planId": plan_id, "planChecksum": promo.get("planChecksum", ""),
            "packageId": "", "packageChecksum": "", "status": "UNKNOWN"}


# ══════════════════════════════════════════════════════════
# 9.2.1-E: Source verification binding
# ══════════════════════════════════════════════════════════

def _reload_source_evidence(promo: dict) -> dict:
    """Authoritative reload: Execution→Observation→Validation→Verification→Evidence."""
    src_exec_id = promo.get("sourceExecutionId", "")
    result = {"executionVerified": False, "observationAvailable": False,
              "validationPassed": False, "verificationPassed": False,
              "evidencePersisted": False, "evidenceDigestMatch": False, "blocks": []}

    if not src_exec_id:
        return result

    run = _exec_db.load_run(src_exec_id)
    if not run:
        result["blocks"].append("SOURCE_EXECUTION_NOT_FOUND")
        return result

    status = run.get("status", "")
    if status == "COMPLETED":
        result["executionVerified"] = True
    else:
        result["blocks"].append(f"SOURCE_EXECUTION_NOT_COMPLETED:{status}")

    validation = run.get("validation", {})
    if isinstance(validation, dict) and validation.get("result") == "PASS":
        result["validationPassed"] = True
    else:
        result["blocks"].append("SOURCE_VALIDATION_NOT_PASSED")

    verification = run.get("verification", {})
    if isinstance(verification, dict) and verification.get("result") == "PASS":
        result["verificationPassed"] = True
    else:
        result["blocks"].append("SOURCE_VERIFICATION_NOT_PASSED")

    evidence = _exec_db.load_evidence(src_exec_id)
    if evidence:
        result["evidencePersisted"] = True
        stored_digest = promo.get("sourceEvidenceDigest", "")
        if stored_digest:
            ev_digest = _digest({"runId": src_exec_id, "evidenceCount": len(evidence)})
            if stored_digest != ev_digest:
                result["blocks"].append("SOURCE_EVIDENCE_DIGEST_MISMATCH")
    else:
        result["blocks"].append("SOURCE_EVIDENCE_MISSING")

    return result


# ══════════════════════════════════════════════════════════
# Digest helpers
# ══════════════════════════════════════════════════════════

def _compute_promotion_digest(promo: dict) -> str:
    """9.2.1-F: Canonical digest binding all security-critical fields."""
    critical = {
        "promotionId": promo.get("promotionId"),
        "sourceEnvId": promo.get("sourceEnvId"), "targetEnvId": promo.get("targetEnvId"),
        "implementationPlanId": promo.get("implementationPlanId"),
        "executionPackageId": promo.get("executionPackageId"),
        "planChecksum": promo.get("planChecksum"),
        "packageChecksum": promo.get("packageChecksum"),
        "sourceExecutionId": promo.get("sourceExecutionId"),
        "sourceVerificationId": promo.get("sourceVerificationId"),
        "sourceEvidenceDigest": promo.get("sourceEvidenceDigest"),
        "blastRadius": promo.get("blastRadius"),
        "maintenanceWindowId": promo.get("maintenanceWindowId"),
        "rollbackPlanId": promo.get("rollbackPlanId"),
        "uatId": promo.get("uatId"),
        "requestedBy": promo.get("requestedBy"),
        "status": promo.get("status"),
        "createdAt": promo.get("createdAt"),
        "expiresAt": promo.get("expiresAt"),
    }
    return _digest(critical)


def _compute_rollback_digest(rb: dict) -> str:
    critical = {
        "rollbackId": rb.get("rollbackId"), "environmentId": rb.get("environmentId"),
        "promotionId": rb.get("promotionId"),
        "implementationPlanId": rb.get("implementationPlanId"),
        "executionPackageId": rb.get("executionPackageId"),
        "triggerConditions": rb.get("triggerConditions"),
        "rollbackSteps": rb.get("rollbackSteps"),
        "verificationSteps": rb.get("verificationSteps"),
        "expectedRecoveryState": rb.get("expectedRecoveryState"),
        "owner": rb.get("owner"), "maxDurationSeconds": rb.get("maxDurationSeconds"),
        "status": rb.get("status"), "createdAt": rb.get("createdAt"),
    }
    return _digest(critical)


def _compute_uat_digest(uat: dict) -> str:
    critical = {
        "uatId": uat.get("uatId"), "promotionId": uat.get("promotionId"),
        "environmentId": uat.get("environmentId"),
        "implementationPlanId": uat.get("implementationPlanId"),
        "executionPackageId": uat.get("executionPackageId"),
        "scope": uat.get("scope"), "acceptanceCriteria": uat.get("acceptanceCriteria"),
        "requestedBy": uat.get("requestedBy"),
        "status": uat.get("status"),
    }
    return _digest(critical)


# ══════════════════════════════════════════════════════════
# ROUTE REGISTRATION
# ══════════════════════════════════════════════════════════

def register_promotion_routes(app: FastAPI) -> None:
    sandbox = create_sandbox_environment("123456789012", "us-east-1")
    cr = create_controlled_real_target("123456789012", "us-east-1")
    prod = EnvironmentTarget(environment_id="ENV-PROD-001", name="Production",
        classification=EnvironmentClassification.PRODUCTION,
        provider="aws", account_id="123456789012", region="us-east-1",
        blast_radius=BlastRadius.CRITICAL, production=True)
    for e in [sandbox, cr, prod]:
        _environments[e.environment_id] = e

    def _env(eid: str):
        e = _environments.get(eid)
        if not e: raise HTTPException(404, "Environment not found")
        return e

    @app.get("/api/v1/environments")
    async def list_environments():
        return {"environments": [e.to_dict() for e in _environments.values()]}

    # ══════════════════════════════════════════════════════
    # PROMOTIONS
    # ══════════════════════════════════════════════════════

    @app.post("/api/v1/promotions")
    async def create_promotion(body: dict[str, Any]):
        src = _env(body.get("sourceEnvironmentId",""))
        tgt = _env(body.get("targetEnvironmentId",""))
        valid, msg = validate_transition(src.classification, tgt.classification)
        if not valid:
            raise HTTPException(400, detail={"error": msg})

        promo_id = f"PROMO-{uuid4().hex[:8].upper()}"
        promo = {
            "promotionId": promo_id,
            "sourceEnvId": src.environment_id, "targetEnvId": tgt.environment_id,
            "sourceEnvClass": src.classification.value, "targetEnvClass": tgt.classification.value,
            "implementationPlanId": body.get("implementationPlanId",""),
            "executionPackageId": body.get("executionPackageId",""),
            "planChecksum": body.get("planChecksum",""),
            "packageChecksum": body.get("packageChecksum",""),
            "sourceExecutionId": body.get("sourceExecutionId",""),
            "sourceVerificationId": body.get("sourceVerificationId",""),
            "sourceEvidenceDigest": body.get("sourceEvidenceDigest",""),
            "blastRadius": tgt.blast_radius.value,
            "maintenanceWindowId": body.get("maintenanceWindowId",""),
            "rollbackPlanId": body.get("rollbackPlanId",""),
            "uatId": body.get("uatId",""),
            "requestedBy": body.get("requestedBy",""),
            "approvedBy": "",
            "status": "PENDING_APPROVAL",
            "promotionDigest": "",
            "createdAt": _now(), "approvedAt": "", "consumedAt": "", "expiresAt": body.get("expiresAt",""),
            "version": "1",
        }
        promo["promotionDigest"] = _compute_promotion_digest(promo)
        persist.persist_promotion(promo)
        return {"promotion": promo}

    @app.get("/api/v1/promotions")
    async def list_promotions():
        return {"promotions": persist.list_promotions()}

    @app.get("/api/v1/promotions/{promotion_id}")
    async def get_promotion(promotion_id: str):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404, "Promotion not found")
        return {"promotion": p}

    @app.post("/api/v1/promotions/{promotion_id}/approve")
    async def approve_promotion(promotion_id: str, approved_by: str = ""):
        # 9.2.1-B: ALWAYS reload from persistence
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        if p["status"] != "PENDING_APPROVAL":
            raise HTTPException(400, detail={"error": f"Status is {p['status']}"})
        if p["requestedBy"] == approved_by:
            raise HTTPException(400, detail={"error": "SEPARATION_OF_DUTIES_VIOLATION"})

        # 9.2.1-F: Verify digest before approval
        current_digest = _compute_promotion_digest(p)
        if current_digest != p.get("promotionDigest", ""):
            p["status"] = "INVALIDATED"
            persist.persist_promotion(p)
            raise HTTPException(400, detail={"error": "PROMOTION_PACKAGE_INVALIDATED"})

        # 9.2.1-D: Authoritative plan/package rebind
        plan = _reload_plan(p)
        if plan and plan.get("planChecksum"):
            if p.get("planChecksum") and p["planChecksum"] != plan["planChecksum"]:
                p["status"] = "INVALIDATED"
                persist.persist_promotion(p)
                raise HTTPException(400, detail={"error": "PROMOTION_INVALIDATED", "reason": "plan checksum changed"})

        # 9.2.1-E: Source verification binding
        src_evidence = _reload_source_evidence(p)
        if src_evidence["blocks"]:
            p["status"] = "INVALIDATED"
            persist.persist_promotion(p)
            raise HTTPException(400, detail={"error": "SOURCE_VERIFICATION_REQUIRED", "blocks": src_evidence["blocks"]})

        p["status"] = "APPROVED"
        p["approvedBy"] = approved_by
        p["approvedAt"] = _now()
        p["promotionDigest"] = _compute_promotion_digest(p)
        persist.persist_promotion(p)
        return {"promotionId": promotion_id, "status": "APPROVED"}

    @app.post("/api/v1/promotions/{promotion_id}/reject")
    async def reject_promotion(promotion_id: str):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        p["status"] = "REJECTED"
        persist.persist_promotion(p)
        return {"promotionId": promotion_id, "status": "REJECTED"}

    @app.post("/api/v1/promotions/{promotion_id}/consume")
    async def consume_promotion(promotion_id: str):
        # 9.2.1-B + 9.2.1-C: Reload from persistence, single-use
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        if p["status"] != "APPROVED":
            raise HTTPException(400, detail={"error": f"Status is {p['status']}, not APPROVED"})
        if p.get("consumedAt"):
            raise HTTPException(400, detail={"error": "PROMOTION_PACKAGE_ALREADY_CONSUMED"})

        current_digest = _compute_promotion_digest(p)
        if current_digest != p.get("promotionDigest", ""):
            p["status"] = "INVALIDATED"
            persist.persist_promotion(p)
            raise HTTPException(400, detail={"error": "PROMOTION_PACKAGE_INVALIDATED_AT_CONSUME"})

        p["status"] = "CONSUMED"
        p["consumedAt"] = _now()
        p["promotionDigest"] = _compute_promotion_digest(p)
        persist.persist_promotion(p)
        return {"promotionId": promotion_id, "status": "CONSUMED"}

    @app.get("/api/v1/promotions/{promotion_id}/verify")
    async def verify_promotion(promotion_id: str):
        p = persist.load_promotion(promotion_id)
        if not p: raise HTTPException(404)
        current = _compute_promotion_digest(p)
        valid = (current == p.get("promotionDigest",""))
        if not valid:
            p["status"] = "INVALIDATED"
            persist.persist_promotion(p)
        return {"promotionId": promotion_id, "valid": valid, "currentDigest": current,
                "storedDigest": p.get("promotionDigest","")}

    # ══════════════════════════════════════════════════════
    # ROLLBACK (Phase 9.3)
    # ══════════════════════════════════════════════════════

    @app.post("/api/v1/rollback-plans")
    async def create_rollback(body: dict[str, Any]):
        rb_id = f"RBP-{uuid4().hex[:8].upper()}"
        rb = {
            "rollbackId": rb_id, "environmentId": body.get("environmentId",""),
            "promotionId": body.get("promotionId",""),
            "implementationPlanId": body.get("implementationPlanId",""),
            "executionPackageId": body.get("executionPackageId",""),
            "triggerConditions": body.get("triggerConditions",[]),
            "rollbackSteps": body.get("rollbackSteps",[]),
            "verificationSteps": body.get("verificationSteps",[]),
            "expectedRecoveryState": body.get("expectedRecoveryState",""),
            "owner": body.get("owner",""), "approvedBy": "",
            "maxDurationSeconds": body.get("maxDurationSeconds",300),
            "createdAt": _now(), "approvedAt": "", "executedAt": "",
            "expiresAt": body.get("expiresAt",""),
            "rollbackDigest": "", "status": "DRAFT",
        }
        rb["rollbackDigest"] = _compute_rollback_digest(rb)
        persist.persist_rollback(rb)
        return {"rollbackPlan": rb}

    @app.get("/api/v1/rollback-plans")
    async def list_rollbacks():
        return {"rollbackPlans": persist.list_rollbacks()}

    @app.get("/api/v1/rollback-plans/{rollback_id}")
    async def get_rollback(rollback_id: str):
        rb = persist.load_rollback(rollback_id)
        if not rb: raise HTTPException(404)
        return {"rollbackPlan": rb}

    @app.post("/api/v1/rollback-plans/{rollback_id}/approve")
    async def approve_rollback(rollback_id: str, approved_by: str = ""):
        rb = persist.load_rollback(rollback_id)
        if not rb: raise HTTPException(404)
        if rb["status"] not in ("DRAFT", "READY"):
            raise HTTPException(400, detail={"error": f"Status is {rb['status']}"})
        current_digest = _compute_rollback_digest(rb)
        if current_digest != rb.get("rollbackDigest", ""):
            rb["status"] = "INVALIDATED"
            persist.persist_rollback(rb)
            raise HTTPException(400, detail={"error": "ROLLBACK_PLAN_INVALIDATED"})
        rb["status"] = "APPROVED"
        rb["approvedBy"] = approved_by
        rb["approvedAt"] = _now()
        rb["rollbackDigest"] = _compute_rollback_digest(rb)
        persist.persist_rollback(rb)
        return {"rollbackId": rollback_id, "status": "APPROVED"}

    # ══════════════════════════════════════════════════════
    # UAT (Phase 9.4)
    # ══════════════════════════════════════════════════════

    @app.post("/api/v1/uat")
    async def create_uat(body: dict[str, Any]):
        uat_id = f"UAT-{uuid4().hex[:8].upper()}"
        uat = {
            "uatId": uat_id, "promotionId": body.get("promotionId",""),
            "environmentId": body.get("environmentId",""),
            "implementationPlanId": body.get("implementationPlanId",""),
            "executionPackageId": body.get("executionPackageId",""),
            "scope": body.get("scope",""), "acceptanceCriteria": body.get("acceptanceCriteria",""),
            "requestedBy": body.get("requestedBy",""),
            "performedBy": "", "approvedBy": "",
            "status": "NOT_STARTED", "uatEvidenceDigest": "",
            "uatDigest": "",
            "startedAt": "", "completedAt": "", "expiresAt": body.get("expiresAt",""),
        }
        uat["uatDigest"] = _compute_uat_digest(uat)
        persist.persist_uat(uat)
        return {"uat": uat}

    @app.get("/api/v1/uat")
    async def list_uats():
        return {"uats": persist.list_uats()}

    @app.get("/api/v1/uat/{uat_id}")
    async def get_uat(uat_id: str):
        u = persist.load_uat(uat_id)
        if not u: raise HTTPException(404)
        return {"uat": u}

    @app.post("/api/v1/uat/{uat_id}/pass")
    async def pass_uat(uat_id: str, performed_by: str = "", approved_by: str = ""):
        u = persist.load_uat(uat_id)
        if not u: raise HTTPException(404)
        if performed_by == approved_by:
            raise HTTPException(400, detail={"error": "SEPARATION_OF_DUTIES_VIOLATION"})
        # 9.4-B: UAT immutability
        current_digest = _compute_uat_digest(u)
        if current_digest != u.get("uatDigest", ""):
            u["status"] = "INVALIDATED"
            persist.persist_uat(u)
            raise HTTPException(400, detail={"error": "UAT_INVALIDATED"})
        u["status"] = "PASSED"
        u["performedBy"] = performed_by
        u["approvedBy"] = approved_by
        u["completedAt"] = _now()
        u["uatEvidenceDigest"] = _digest({"uatId": uat_id, "passedAt": _now(), "performedBy": performed_by})
        u["uatDigest"] = _compute_uat_digest(u)
        persist.persist_uat(u)
        return {"uatId": uat_id, "status": "PASSED"}

    @app.post("/api/v1/uat/{uat_id}/fail")
    async def fail_uat(uat_id: str):
        u = persist.load_uat(uat_id)
        if not u: raise HTTPException(404)
        u["status"] = "FAILED"
        persist.persist_uat(u)
        return {"uatId": uat_id, "status": "FAILED"}

    # ══════════════════════════════════════════════════════
    # PRODUCTION READINESS (Phase 9.5)
    # ══════════════════════════════════════════════════════

    @app.post("/api/v1/production-readiness/evaluate")
    async def evaluate_readiness(body: dict[str, Any]):
        rd_id = f"RDY-{uuid4().hex[:8].upper()}"
        blocks = []
        warnings = []

        promo_id = body.get("promotionId","")
        uat_id = body.get("uatId","")
        rollback_id = body.get("rollbackPlanId","")
        env_id = body.get("environmentId","")
        plan_cs = body.get("planChecksum","")
        pkg_cs = body.get("packageChecksum","")

        # 9.5-B: Gates
        if not body.get("planId"):
            blocks.append("PLAN_ID_NOT_PROVIDED")
        if not body.get("packageId"):
            blocks.append("PACKAGE_ID_NOT_PROVIDED")
        if plan_cs and pkg_cs and plan_cs != pkg_cs:
            blocks.append("PLAN_PACKAGE_CHECKSUM_MISMATCH")

        # Promotion gate
        promo = None
        if promo_id:
            promo = persist.load_promotion(promo_id)
            if not promo:
                blocks.append("PROMOTION_NOT_FOUND")
            else:
                if promo["status"] != "APPROVED":
                    blocks.append(f"PROMOTION_NOT_APPROVED:{promo['status']}")
                if promo.get("consumedAt"):
                    blocks.append("PROMOTION_ALREADY_CONSUMED")
                expires = promo.get("expiresAt","")
                if expires and expires < _now():
                    blocks.append("PROMOTION_EXPIRED")
                current_digest = _compute_promotion_digest(promo)
                if current_digest != promo.get("promotionDigest",""):
                    blocks.append("PROMOTION_DIGEST_INVALID")
                if promo.get("planChecksum") and plan_cs and promo["planChecksum"] != plan_cs:
                    blocks.append("PLAN_CHECKSUM_MISMATCH_WITH_PROMOTION")
                if promo.get("packageChecksum") and pkg_cs and promo["packageChecksum"] != pkg_cs:
                    blocks.append("PACKAGE_CHECKSUM_MISMATCH_WITH_PROMOTION")
        else:
            blocks.append("PROMOTION_REQUIRED")

        # Blast radius
        br = promo.get("blastRadius","") if promo else ""
        if not br:
            blocks.append("BLAST_RADIUS_NOT_DEFINED")
        elif br == "CRITICAL":
            warnings.append("BLAST_RADIUS_CRITICAL")

        # Rollback
        if rollback_id:
            rb = persist.load_rollback(rollback_id)
            if not rb:
                blocks.append("ROLLBACK_NOT_FOUND")
            else:
                if rb["status"] != "APPROVED":
                    blocks.append(f"ROLLBACK_NOT_APPROVED:{rb['status']}")
                current_rb_digest = _compute_rollback_digest(rb)
                if current_rb_digest != rb.get("rollbackDigest",""):
                    blocks.append("ROLLBACK_DIGEST_INVALID")
                if rb.get("expiresAt","") and rb["expiresAt"] < _now():
                    blocks.append("ROLLBACK_EXPIRED")
        else:
            blocks.append("ROLLBACK_REQUIRED")

        # UAT
        if uat_id:
            uat = persist.load_uat(uat_id)
            if not uat:
                blocks.append("UAT_NOT_FOUND")
            else:
                if uat["status"] != "PASSED":
                    blocks.append(f"UAT_NOT_PASSED:{uat['status']}")
                current_uat_digest = _compute_uat_digest(uat)
                if current_uat_digest != uat.get("uatDigest",""):
                    blocks.append("UAT_DIGEST_INVALID")
                if uat.get("expiresAt","") and uat["expiresAt"] < _now():
                    blocks.append("UAT_EXPIRED")
        else:
            blocks.append("UAT_REQUIRED")

        # SoD
        if promo:
            if promo.get("requestedBy") == promo.get("approvedBy") and promo.get("requestedBy"):
                blocks.append("PROMOTION_SOD_VIOLATION")
            if not promo.get("approvedBy"):
                blocks.append("PROMOTION_APPROVER_MISSING")

        # Cost
        cost_est = body.get("costEstimate")
        cost_ceil = body.get("costCeiling")
        if cost_est is not None and cost_ceil is not None:
            try:
                if float(cost_est) > float(cost_ceil):
                    blocks.append("COST_EXCEEDED")
            except (ValueError, TypeError):
                warnings.append("COST_CHECK_SKIPPED")

        # Ownership
        if not body.get("ownershipScope"):
            warnings.append("OWNERSHIP_SCOPE_NOT_VERIFIED")
        if not body.get("maintenanceWindowId"):
            warnings.append("MAINTENANCE_WINDOW_NOT_SPECIFIED")

        decision = "READY" if not blocks else "NOT_READY"

        rd = {
            "readinessId": rd_id,
            "promotionId": promo_id,
            "environmentId": env_id,
            "planId": body.get("planId",""),
            "packageId": body.get("packageId",""),
            "planChecksum": plan_cs,
            "packageChecksum": pkg_cs,
            "blocks": blocks,
            "warnings": warnings,
            "readinessDecision": decision,
            "dependencyDigests": {
                "promotionDigest": promo.get("promotionDigest","") if promo else "",
                "promotionStatus": promo.get("status","") if promo else "",
            },
            "readinessDigest": "",
            "evaluatedAt": _now(),
            "expiresAt": _now(),
        }
        rd["readinessDigest"] = _digest({
            "readinessId": rd_id, "blocks": sorted(blocks),
            "decision": decision, "evaluatedAt": rd["evaluatedAt"]
        })
        persist.persist_readiness(rd)

        # 9.5-E: PRODUCTION always BLOCKED
        return {
            "readiness": rd,
            "PRODUCTION_EXECUTION_ALLOWED": False,
            "PRODUCTION": "BLOCK",
            "gatesEvaluated": len(blocks) + len(warnings),
            "gatesBlocked": len(blocks),
        }

    @app.get("/api/v1/production-readiness")
    async def list_readiness():
        return {"readinessRecords": persist.list_readiness()}

    @app.get("/api/v1/production-readiness/{readiness_id}")
    async def get_readiness(readiness_id: str):
        rd = persist.load_readiness(readiness_id)
        if not rd: raise HTTPException(404)
        return {"readiness": rd, "PRODUCTION_EXECUTION_ALLOWED": False, "PRODUCTION": "BLOCK"}

    # ══════════════════════════════════════════════════════
    # WORKSPACE (Phase 11.5)
    # ══════════════════════════════════════════════════════
    @app.post("/api/v1/workspaces")
    async def create_workspace(body: dict[str, Any]):
        ws_id = f"WS-{uuid4().hex[:8].upper()}"
        ws = {
            "workspaceId": ws_id, "name": body.get("name",""),
            "currentDesignId": "", "currentPlanId": "",
            "currentPackageId": "", "currentRunId": "",
            "selectedProvider": body.get("provider",""),
            "selectedPlatform": body.get("platform",""),
            "selectedFidelity": body.get("fidelity","LOCAL_RUNTIME"),
            "createdAt": _now(), "updatedAt": _now(),
        }
        persist.persist_workspace(ws)
        return {"workspace": ws}

    @app.get("/api/v1/workspaces")
    async def list_workspaces():
        return {"workspaces": persist.list_workspaces()}

    @app.get("/api/v1/workspaces/{workspace_id}")
    async def get_workspace(workspace_id: str):
        ws = persist.load_workspace(workspace_id)
        if not ws: raise HTTPException(404)
        return {"workspace": ws}

    @app.post("/api/v1/workspaces/{workspace_id}/current-design")
    async def set_current_design(workspace_id: str, design_id: str = ""):
        ws = persist.load_workspace(workspace_id)
        if not ws: raise HTTPException(404)
        ws["currentDesignId"] = design_id
        ws["updatedAt"] = _now()
        persist.persist_workspace(ws)
        return {"workspace": ws}

    @app.post("/api/v1/workspaces/{workspace_id}/current-plan")
    async def set_current_plan(workspace_id: str, plan_id: str = ""):
        ws = persist.load_workspace(workspace_id)
        if not ws: raise HTTPException(404)
        ws["currentPlanId"] = plan_id
        ws["updatedAt"] = _now()
        persist.persist_workspace(ws)
        return {"workspace": ws}

    @app.post("/api/v1/workspaces/{workspace_id}/current-package")
    async def set_current_package(workspace_id: str, package_id: str = ""):
        ws = persist.load_workspace(workspace_id)
        if not ws: raise HTTPException(404)
        ws["currentPackageId"] = package_id
        ws["updatedAt"] = _now()
        persist.persist_workspace(ws)
        return {"workspace": ws}

