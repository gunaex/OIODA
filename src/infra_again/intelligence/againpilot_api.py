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
    AgainPilotRequest, AgainPilotProposal, AgainPilotProviderRouter,
    ProviderPreference, PlatformPreference, GenerationDepth,
    AIGenerationMode, get_againpilot, extract_requirements,
)


# ============================================================================
# Request Models
# ============================================================================


class GenerateRequest(BaseModel):
    brief: str
    providerPreference: str = "AUTO"
    platformPreference: str = "AUTO"
    generationDepth: str = "HIGH_LEVEL"
    constraints: dict[str, list[str]] = {}


class RefineRequest(BaseModel):
    instruction: str
    nodes: list[dict] = []
    edges: list[dict] = []
    provider: str = "AWS"


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
            proposal = againpilot.generate(request)
            # Run quality validation
            from .againpilot import validate_architecture_quality
            node_dicts = [n.to_dict() for n in proposal.nodes]
            edge_dicts = [e.to_dict() for e in proposal.edges]
            group_dicts = [g.to_dict() for g in proposal.groups]
            quality = validate_architecture_quality(
                node_dicts, edge_dicts, group_dicts,
                proposal.detected_requirements.provider,
                proposal.detected_requirements,
                "LLM_GENERATED" if againpilot.mode.value == "REAL_LLM" else "DETERMINISTIC",
            )
            return {
                "proposal": proposal.to_dict(),
                "quality": quality.to_dict(),
                "generationMode": againpilot.mode.value,
                "generationProvider": againpilot.provider_name,
                "generationModel": againpilot.model_name,
            }
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    # ── Refine Architecture ──

    @app.post("/api/v1/againpilot/refine")
    async def againpilot_refine(body: RefineRequest):
        """Refine existing architecture with natural language instruction."""
        try:
            proposal, delta = againpilot.refine(body.nodes, body.edges, body.instruction, body.provider)
            return {
                "proposal": proposal.to_dict(),
                "delta": delta.to_dict(),
            }
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

    # ── Legacy: Keep old endpoint for backward compat ──
    # (Redirects to new AGAINPILOT generate)

    @app.post("/api/v1/designs/{design_id}/ai-generate")
    async def ai_generate_design_legacy(design_id: str, body: dict[str, Any] | None = None):
        """Legacy endpoint — delegates to AGAINPILOT."""
        brief = (body or {}).get("brief", {})
        brief_text = brief.get("objective", "") + " " + brief.get("components", "")
        provider = brief.get("provider", "AWS")
        platform = brief.get("platform", "KUBERNETES")

        request = AgainPilotRequest(
            brief=brief_text or f"Generate architecture on {provider} using {platform}",
            provider_preference=_parse_enum(provider, ProviderPreference),
            platform_preference=_parse_enum(platform, PlatformPreference),
        )
        proposal = againpilot.generate(request)
        return {
            "designId": design_id,
            "proposal": proposal.to_dict(),
            "provider": provider,
            "platform": platform,
            "status": "AI_GENERATED",
        }


def _parse_enum(value: str, enum_cls: type) -> Any:
    """Safely parse enum value with fallback to AUTO."""
    try:
        return enum_cls(value.upper())
    except (ValueError, AttributeError):
        # Return first member (usually AUTO)
        return next(iter(enum_cls))
