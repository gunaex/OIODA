"""AGAINPILOT API Routes.

Phase C: Natural language → Canonical Architecture → draw.io.
All LLM/provider calls happen server-side. No secrets exposed to frontend.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .againpilot import (
    AgainPilotRequest, DetectedRequirement,
    ProviderPreference, PlatformPreference, GenerationDepth,
    AIGenerationMode, RealAIGenerationFailed, get_againpilot, extract_requirements,
    validate_architecture_completeness,
)

# Import flow persistence for designId-based lifecycle checks
import os as _os, json as _json
from pathlib import Path as _Path
FLOW_DB_PATH = _os.environ.get("INFRA_AGAIN_DB", str(_Path(".ai/infra-again.db").resolve()))

def _get_design_from_db(design_id: str) -> dict | None:
    """Load a design's status + flow from SQLite. Returns None if not found."""
    import sqlite3
    try:
        conn = sqlite3.connect(FLOW_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, flow_json FROM flow_designs WHERE design_id = ?",
            (design_id,),
        ).fetchone()
        conn.close()
        if row:
            return {"status": row["status"], "flow_json": row["flow_json"] or ""}
        return None
    except Exception:
        return None


# ============================================================================
# Request Models
# ============================================================================


class GenerateRequest(BaseModel):
    brief: str
    providerPreference: str = "AUTO"
    platformPreference: str = "AUTO"
    generationDepth: str = "HIGH_LEVEL"
    constraints: dict[str, list[str]] = {}
    # Explicit user consent to skip real AI and use the deterministic
    # generator. Only "DETERMINISTIC_FALLBACK" has any effect; anything else
    # (including empty) means "try real AI, ask me before falling back".
    forceMode: str = ""


class RefineRequest(BaseModel):
    instruction: str
    designId: str = ""  # If set, backend resolves authoritative design + lifecycle
    nodes: list[dict] = []
    edges: list[dict] = []
    provider: str = "AWS"
    forceMode: str = ""
    # The generating proposal's detectedRequirements (camelCase, as returned
    # by /generate). Used so refine's post-change quality/completeness
    # re-check doesn't lose the original brief's HA/compliance/security
    # signals — see _merge_refine_requirements.
    detectedRequirements: dict[str, Any] = {}


class ExplainRequest(BaseModel):
    nodes: list[dict] = []
    edges: list[dict] = []
    provider: str = "AWS"


class SecurityAnalysisRequest(BaseModel):
    nodes: list[dict] = []
    edges: list[dict] = []
    brief: str = ""


# ============================================================================
# Route Registration
# ============================================================================


def register_againpilot_routes(app: FastAPI) -> None:
    """Register all AGAINPILOT API routes."""

    againpilot = get_againpilot()

    # ── Provider Status ──

    @app.get("/api/v1/againpilot/status")
    async def againpilot_status():
        """Return current AI provider status. Never exposes secrets."""
        return {
            "mode": againpilot.mode.value,
            "provider": againpilot.provider_name,
            "model": againpilot.model_name,
            "available": againpilot.mode != AIGenerationMode.UNAVAILABLE,
        }

    # ── Generate Architecture ──

    @app.post("/api/v1/againpilot/generate")
    async def againpilot_generate(body: GenerateRequest):
        """Generate architecture proposal from natural language brief.

        All generation happens server-side. Provider secrets never reach frontend.
        """
        try:
            request = AgainPilotRequest(
                brief=body.brief,
                provider_preference=_parse_enum(body.providerPreference, ProviderPreference),
                platform_preference=_parse_enum(body.platformPreference, PlatformPreference),
                generation_depth=_parse_enum(body.generationDepth, GenerationDepth),
                constraints=body.constraints,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

        try:
            try:
                proposal = againpilot.generate(request, force_mode=body.forceMode or None)
            except RealAIGenerationFailed as fail:
                # Real AI failed and the caller did not pass forceMode —
                # this is NOT a server error. Return 200 with an explicit
                # consent request; the deterministic generator has NOT run.
                prov = fail.provenance
                return {
                    "needsFallbackConsent": True,
                    "resultMode": prov.get("result") or prov.get("finalResultMode") or "FAILED",
                    "provenance": _provenance_dict(prov),
                }

            from .againpilot import validate_architecture_quality
            node_dicts = [n.to_dict() for n in proposal.nodes]
            edge_dicts = [e.to_dict() for e in proposal.edges]
            group_dicts = [g.to_dict() for g in proposal.groups]
            quality = validate_architecture_quality(
                node_dicts, edge_dicts, group_dicts,
                proposal.detected_requirements.provider,
                proposal.detected_requirements,
                "LLM_TWO_STAGE" if againpilot.mode.value == "REAL_LLM" else "DETERMINISTIC",
            )
            completeness = validate_architecture_completeness(
                node_dicts, edge_dicts, proposal.detected_requirements,
            )
            prov = againpilot.last_provenance
            return {
                "proposal": proposal.to_dict(),
                "quality": quality.to_dict(),
                "completeness": completeness.to_dict(),
                "generationMode": againpilot.mode.value,
                "generationProvider": againpilot.provider_name,
                "generationModel": againpilot.model_name,
                "resultMode": againpilot.last_result_mode or prov.get("result", "UNKNOWN"),
                "provenance": _provenance_dict(prov, fallback_mode=againpilot.mode.value, fallback_result=againpilot.last_result_mode),
            }
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    # ── Refine Architecture ──

    @app.post("/api/v1/againpilot/refine")
    async def againpilot_refine(body: RefineRequest):
        """Refine existing architecture with natural language instruction.

        When designId is provided the backend resolves the authoritative
        design from persistence and checks its lifecycle status BEFORE
        any AI/LLM work — frozen designs are rejected immediately.
        """
        # ── Lifecycle guard ────────────────────────────────────────
        nodes = body.nodes
        edges = body.edges

        if body.designId:
            design = _get_design_from_db(body.designId)
            if design is None:
                raise HTTPException(status_code=404, detail=f"Design not found: {body.designId}")
            if design["status"] in ("BASELINE_FROZEN", "FROZEN", "ACCEPTED"):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot edit accepted/frozen design",
                )
            # Use authoritative flow from persistence, not frontend-supplied
            if design.get("flow_json"):
                try:
                    flow = _json.loads(design["flow_json"])
                    nodes = flow.get("nodes", nodes)
                    edges = flow.get("edges", edges)
                except Exception:
                    pass  # fall back to request-supplied nodes/edges

        try:
            base_req = _parse_detected_requirements(body.detectedRequirements)
            try:
                proposal, delta = againpilot.refine(
                    nodes, edges, body.instruction, body.provider,
                    force_mode=body.forceMode or None, base_req=base_req,
                )
            except RealAIGenerationFailed as fail:
                prov = fail.provenance
                return {
                    "needsFallbackConsent": True,
                    "resultMode": prov.get("result") or prov.get("finalResultMode") or "FAILED",
                    "provenance": _provenance_dict(prov),
                }
            node_dicts = [n.to_dict() for n in proposal.nodes]
            edge_dicts = [e.to_dict() for e in proposal.edges]
            completeness = validate_architecture_completeness(node_dicts, edge_dicts, proposal.detected_requirements)
            prov = againpilot.last_provenance
            return {
                "proposal": proposal.to_dict(),
                "delta": delta.to_dict(),
                "completeness": completeness.to_dict(),
                "resultMode": againpilot.last_result_mode or prov.get("result", "UNKNOWN"),
                "provenance": _provenance_dict(prov),
            }
        except HTTPException:
            raise
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid refinement input: {e}")
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Refinement failed: {e}")

    # ── Explain Architecture ──

    @app.post("/api/v1/againpilot/explain")
    async def againpilot_explain(body: ExplainRequest):
        """Explain the current architecture in plain language."""
        try:
            explanation = againpilot.explain(body.nodes, body.edges, body.provider)
            return {"explanation": explanation}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Explain failed: {e}")

    # ── Security Analysis ──

    @app.post("/api/v1/againpilot/security-analysis")
    async def againpilot_security_analysis(body: SecurityAnalysisRequest):
        """Analyze security posture of the architecture."""
        try:
            req = extract_requirements(body.brief) if body.brief else extract_requirements("")
            analysis = againpilot.analyze_security(body.nodes, body.edges, req)
            return {"analysis": analysis.to_dict()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Security analysis failed: {e}")

    # ── Requirement Extraction ──

    @app.post("/api/v1/againpilot/extract-requirements")
    async def againpilot_extract(body: GenerateRequest):
        """Extract structured requirements from brief without full generation."""
        try:
            req = extract_requirements(body.brief)
            return {"requirements": req.to_dict()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    # NOTE: there is intentionally no duplicate "/api/v1/designs/{design_id}/ai-generate"
    # registration here. flow/api.py registers that exact path first (see
    # register_flow_routes in api/__init__.py, called before
    # register_againpilot_routes), so FastAPI/Starlette always dispatches to
    # that handler — a second registration of the same path here was dead
    # code that could never run, despite its docstring claiming it "delegates
    # to AGAINPILOT". The real AGAINPILOT engine is reachable only via
    # POST /api/v1/againpilot/generate, which is what the UI actually calls.


def _parse_detected_requirements(d: dict[str, Any]) -> DetectedRequirement | None:
    """Parse the camelCase detectedRequirements dict (as returned by
    /generate's proposal.detectedRequirements) back into a DetectedRequirement.
    Returns None if the frontend didn't send one (e.g. refining a hand-built
    canvas with no prior AGAINPILOT proposal)."""
    if not d:
        return None
    return DetectedRequirement(
        provider=d.get("provider", "ON_PREM"),
        platform=d.get("platform", "NATIVE_VM"),
        expected_load=d.get("expectedLoad", "UNKNOWN"),
        availability=list(d.get("availability", [])),
        compliance=list(d.get("compliance", [])),
        security=list(d.get("security", [])),
        data_sensitivity=list(d.get("dataSensitivity", [])),
    )


def _provenance_dict(prov: dict, fallback_mode: str = "", fallback_result: str = "") -> dict:
    """Normalize the internal provenance dict into the canonical field set.

    Distinct fields for requested vs. actual result mode, and for which
    generator produced the first pass vs. any correction pass, so the
    frontend never has to infer provenance from a single ambiguous string.

    Two shapes flow through here: the single-provider AgainPilotProviderRouter
    shape (mode/result/provider/model/stage1Ms/...) and, when the M3 hybrid
    router is active, RoutingProvenance.to_dict() (requestPolicy/localModel/
    cloudProvider/finalResultMode/...) — a disjoint field set. Previously this
    function only understood the first shape, so any hybrid-routed response
    (including every real DeepSeek/OpenAI call) surfaced an all-empty/default
    provenance block to the API caller despite the router having captured
    everything correctly internally.
    """
    is_routed = "requestPolicy" in prov
    final_mode = prov.get("finalResultMode", "")
    used_cloud = final_mode in ("CLOUD_ESCALATED", "CLOUD_DIRECT")

    if is_routed:
        generation_provider = prov.get("cloudProvider", "") if used_cloud else ("LOCAL_LLM" if prov.get("localModel") else "")
        generation_model = prov.get("cloudModel", "") if used_cloud else prov.get("localModel", "")
        result_mode = final_mode or fallback_result or "UNKNOWN"
    else:
        generation_provider = prov.get("provider", "")
        generation_model = prov.get("model", "")
        result_mode = prov.get("result", fallback_result or "UNKNOWN")

    out = {
        "generationRequestedMode": prov.get("generationRequestedMode", fallback_mode or prov.get("mode", "") or prov.get("requestPolicy", "")),
        "generationResultMode": result_mode,
        "generationProvider": generation_provider,
        "generationModel": generation_model,
        "firstPassGenerator": prov.get("firstPassGenerator"),
        "correctionGenerator": prov.get("correctionGenerator"),
        "stage1LatencyMs": prov.get("stage1Ms", 0),
        "stage2LatencyMs": prov.get("stage2Ms", 0),
        "correctionLatencyMs": prov.get("correctionMs", 0),
        "briefHash": prov.get("briefHash", ""),
        "generationTimestamp": prov.get("generationTimestamp", ""),
        "qualityResult": prov.get("qualityResult"),
        "completenessResult": prov.get("completenessResult"),
        "userConsented": prov.get("userConsented"),
        # Hybrid-router execution path — present only when the M3 router
        # actually ran. The frontend uses these (not chain-of-thought, not
        # raw model text) to render "Local · X -> Cloud Expert · Y -> Accepted".
        "requestPolicy": prov.get("requestPolicy"),
        "requestType": prov.get("requestType"),
        "localModel": prov.get("localModel"),
        "localResult": prov.get("localResult"),
        "localLatencyMs": prov.get("localLatencyMs"),
        "localCorrectionUsed": prov.get("localCorrectionUsed"),
        "escalated": prov.get("escalated"),
        "escalationReason": prov.get("escalationReason"),
        "cloudProvider": prov.get("cloudProvider"),
        "cloudModel": prov.get("cloudModel"),
        "cloudResult": prov.get("cloudResult"),
        "cloudLatencyMs": prov.get("cloudLatencyMs"),
        "finalResultMode": prov.get("finalResultMode"),
        "tokenUsage": prov.get("tokenUsage"),
        # Deterministic validator output only (gate/result/detail; missing
        # role names) — never the model's raw response or reasoning_content.
        "qualityFailures": prov.get("qualityFailures"),
        "missingRoles": prov.get("missingRoles"),
    }
    return out


def _parse_enum(value: str, enum_cls: type) -> Any:
    """Safely parse enum value with fallback to AUTO."""
    try:
        return enum_cls(value.upper())
    except (ValueError, AttributeError):
        # Return first member (usually AUTO)
        return next(iter(enum_cls))
