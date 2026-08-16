"""
Conductor Again — AI-Powered Intake & Golden Flow
Uses AUTO router + Skills to decompose and analyze with real AI.

E8.1-F: the AI decomposition call routes through LocalAIControlCenterClient.execute_capability()
(the AIExecutionGateway) in ECOSYSTEM_MODE (default) rather than instantiating a DeepSeek
adapter directly with a decrypted AIAccount.api_key_encrypted. The pre-E8.1 direct-adapter
path remains available ONLY when ECOSYSTEM_MODE=false (LEGACY_DIRECT_AI_MODE, dev-only,
disclosed, §34) — it is never reachable in ecosystem mode. The rule-based fallback
(_decompose_text_structured) is unchanged either way.
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_master_db, get_project_db
from app.integration.lacc_client import LocalAIControlCenterClient
from app.models import (
    AIResource,
    DeliberationCase,
    FunctionItem,
    IntakeSession,
    Requirement,
    RiskAssessment,
    SimilarityPair,
    Skill,
    SkillVersion,
    User,
    Vision,
)
from app.r2_storage import build_object_key, generate_download_url, generate_upload_url, is_available, upload_bytes
from app.routers.intake import _categorize, _assign_module

router = APIRouter(prefix="/api/{slug}/golden", tags=["golden-flow"])

ECOSYSTEM_MODE = os.getenv("ECOSYSTEM_MODE", "false").lower() == "true"

_DECOMPOSITION_PROMPT = """You are a requirements decomposition specialist. Analyze the following requirements and output a JSON array of function objects. Each function must have: code (F-001 format), title, description, category (ui/backend/integration/data/security/reporting/feature), complexity (trivial/simple/moderate/complex/very_complex), and target_module (CONDUCTOR/PM_AGAIN/QA_AGAIN/DEV).

Requirements:
{content}

Output ONLY valid JSON array, no other text."""


async def _ai_decompose_via_gateway(content: str, slug: str) -> tuple[list | None, str | None]:
    """AIExecutionGateway path (ECOSYSTEM_MODE): CODE_PLANNING-shaped decomposition
    request, no AIResource/api_key_encrypted lookup at all. Returns (None, None) (falls
    back to rule-based decomposition) on any non-success/non-parseable result — never
    raises."""
    import asyncio
    import json

    correlation_id = f"corr-golden-{uuid.uuid4().hex[:12]}"
    result = await asyncio.to_thread(
        LocalAIControlCenterClient.execute_capability,
        capability="BUSINESS_ANALYSIS",
        correlation_id=correlation_id,
        prompt=_DECOMPOSITION_PROMPT.format(content=content[:5000]),
        request_id=f"req-golden-{uuid.uuid4().hex[:8]}",
    )
    if result.get("status") != "COMPLETED":
        return None, None
    model_used = f"{result.get('providerUsed', 'ollama')}/{result.get('modelUsed', 'unknown')}"
    text = result.get("outputSummary") or ""
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end]), model_used
    except Exception:
        pass
    return None, None


@router.post("/ai-decompose")
async def ai_decompose(
    slug: str,
    body: dict,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """AI-powered decomposition: finds the best available AI resource and decomposes intelligently."""
    content = body.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Content required")

    # Find decomposition skill
    skill = master_db.query(Skill).filter(Skill.skill_id == "scope-decomposer").first()
    sv = None
    if skill:
        sv = master_db.query(SkillVersion).filter(
            SkillVersion.skill_id == skill.id,
            SkillVersion.status == "published",
        ).order_by(SkillVersion.version.desc()).first()

    # Try AI-powered analysis
    ai_result = None
    ai_model_used = None
    if ECOSYSTEM_MODE:
        ai_result, ai_model_used = await _ai_decompose_via_gateway(content, slug)
    else:
        # ── LEGACY_DIRECT_AI_MODE (dev-only, disclosed, §34) ──
        resources = master_db.query(AIResource).filter(
            AIResource.enabled == True,
            AIResource.health_state.in_(["AVAILABLE", "DEGRADED"]),
        ).all()

        if resources:
            best = sorted(resources, key=lambda r: r.base_priority, reverse=True)[0]
            account = best.account
            if account and account.api_key_encrypted:
                try:
                    from app.routers.ai_resources import _decrypt
                    api_key = _decrypt(account.api_key_encrypted)
                    provider_code = account.provider.code if account.provider else "unknown"
                    model_id = best.model.model_id if best.model else "deepseek-chat"

                    if provider_code == "deepseek" and api_key:
                        from app.adapters.base import AIRequest
                        from app.adapters.deepseek import create_deepseek_adapter
                        adapter = create_deepseek_adapter(api_key)

                        response = await adapter.chat(AIRequest(
                            messages=[{"role": "user", "content": _DECOMPOSITION_PROMPT.format(content=content[:5000])}],
                            model_id=model_id,
                            max_tokens=2000,
                            temperature=0.3,
                        ))
                        import json
                        try:
                            text = response.content or ""
                            start = text.find("[")
                            end = text.rfind("]") + 1
                            if start >= 0 and end > start:
                                ai_result = json.loads(text[start:end])
                                ai_model_used = f"{provider_code}/{model_id}"
                        except Exception:
                            pass  # Fall back to rule-based
                except Exception:
                    pass  # AI failed, fall back to rule-based

    # Create session
    session = IntakeSession(
        source_type=body.get("source_type", "text"),
        source_name=body.get("source_name", f"AI Decomposition - {slug}"),
        raw_content=content[:10000],
        created_by=user.email,
        status="decomposed",
    )
    db.add(session)
    db.flush()

    # Use AI result or fall back to rule-based
    from app.routers.intake import _decompose_text
    from app.complexity import analyze_complexity, complexity_level
    from app.effort import estimate_effort

    functions_raw = ai_result if ai_result else [
        {"title": f["title"], "description": f.get("description", ""),
         "category": f.get("category", ""), "complexity": f.get("complexity", "moderate"),
         "target_module": f.get("target_module", "DEV")}
        for f in _decompose_text_structured(content)
    ] if not ai_result else ai_result

    functions: list[FunctionItem] = []
    for i, fn in enumerate(functions_raw if ai_result else _decompose_text(content)):
        code = f"F-{i + 1:03d}"
        if ai_result:
            title = fn.get("title", fn.get("name", f"Function {i+1}"))
            desc = fn.get("description", "")
            cat = fn.get("category", _categorize(title, desc))
            complexity_hint = fn.get("complexity", "moderate")
            target = fn.get("target_module", _assign_module(title, desc, cat))
        else:
            title = fn["title"]
            desc = fn.get("description", "")
            cat = fn.get("category", _categorize(title, desc))
            complexity_hint = "moderate"
            target = _assign_module(title, desc, cat)

        # Score complexity
        cx = analyze_complexity(title, desc)
        if ai_result and complexity_hint != "moderate":
            # Blend AI hint with computed score
            hint_scores = {"trivial": 10, "simple": 25, "moderate": 50, "complex": 75, "very_complex": 95}
            cx.overall = (cx.overall + hint_scores.get(complexity_hint, 50)) / 2

        eff = estimate_effort(title, desc, cx.overall)

        func = FunctionItem(
            session_id=session.id,
            code=code,
            title=title,
            description=desc[:500],
            category=cat,
            complexity_score=cx.overall,
            complexity_level=complexity_level(cx.overall),
            complexity_breakdown={"structural": cx.structural, "domain": cx.domain, "integration": cx.integration, "data": cx.data, "uncertainty": cx.uncertainty},
            effort_fp=eff.function_points,
            effort_person_days=eff.person_days,
            effort_level=eff.level,
            effort_breakdown=eff.breakdown,
            target_module=target,
        )
        db.add(func)
        db.flush()
        functions.append(func)

    # Risk forecast
    from app.risk_forecast import forecast_risks
    func_dicts = [{"title": f.title, "description": f.description, "code": f.code} for f in functions]
    forecast = forecast_risks(func_dicts)
    risk = RiskAssessment(
        session_id=session.id, overall_risk_score=forecast.overall_risk_score,
        level=forecast.level, schedule_buffer_days=forecast.schedule_buffer_days,
        summary=forecast.summary,
        risk_items=[{"category": r.category, "description": r.description,
                      "probability": r.probability, "impact": r.impact,
                      "severity": r.severity, "level": r.level,
                      "mitigation": r.mitigation} for r in forecast.items],
    )
    db.add(risk)
    session.status = "analyzed"
    db.commit()

    return {
        "session_id": session.id,
        "ai_powered": bool(ai_result),
        "ai_model": ai_model_used,
        "function_count": len(functions),
        "total_effort_days": round(sum(f.effort_person_days for f in functions), 1),
        "risk_level": forecast.level,
        "risk_score": forecast.overall_risk_score,
        "schedule_buffer_days": forecast.schedule_buffer_days,
        "functions": [{"code": f.code, "title": f.title, "complexity": f.complexity_level, "effort_days": f.effort_person_days, "target": f.target_module} for f in functions],
        "risk_items": [{"category": r.category, "level": r.level, "mitigation": r.mitigation} for r in forecast.items],
    }


def _decompose_text_structured(text: str) -> list[dict]:
    """Rule-based fallback decomposition."""
    from app.routers.intake import _decompose_text
    return _decompose_text(text)


# ═══════════════════════════════════════════════════════════
# Golden Flow Trigger
# ═══════════════════════════════════════════════════════════

@router.post("/trigger")
def trigger_golden_flow(
    slug: str,
    body: dict,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """One-click golden flow: Vision → Decompose → Analyze → Ready for Deliberation."""
    vision_text = body.get("vision", "")
    if not vision_text.strip():
        raise HTTPException(status_code=400, detail="Vision text required")

    results = {"steps": []}

    # Step 1: Save Vision
    latest = db.query(Vision).order_by(Vision.revision.desc()).first()
    rev = (latest.revision + 1) if latest else 1
    vision = Vision(revision=rev, content=vision_text, created_by=user.email)
    db.add(vision)
    db.flush()
    results["steps"].append({"step": "vision_saved", "revision": rev})

    # Step 2: Extract requirements from vision
    from app.routers.intake import _decompose_text, _categorize
    req_items = _decompose_text(vision_text)
    for i, item in enumerate(req_items[:10]):
        code = f"REQ-{i + 1:03d}"
        # Skip if code already exists
        existing = db.query(Requirement).filter(Requirement.code == code).first()
        if existing:
            continue
        req = Requirement(code=code, title=item["title"][:200], description=item.get("description", "")[:500], created_by=user.email)
        db.add(req)
    db.flush()
    results["steps"].append({"step": "requirements_extracted", "count": len(req_items[:10])})

    # Step 3: Decompose into functions
    session = IntakeSession(source_type="golden_flow", source_name=f"Golden Flow - {slug}", raw_content=vision_text[:5000], created_by=user.email, status="decomposed")
    db.add(session)
    db.flush()

    funcs_raw = _decompose_text(vision_text)
    from app.complexity import analyze_complexity, complexity_level
    from app.effort import estimate_effort

    functions = []
    for i, fn in enumerate(funcs_raw[:15]):
        code = f"F-{i + 1:03d}"
        cx = analyze_complexity(fn["title"], fn.get("description", ""))
        eff = estimate_effort(fn["title"], fn.get("description", ""), cx.overall)
        func = FunctionItem(session_id=session.id, code=code, title=fn["title"], description=fn.get("description", "")[:500],
                            category=_categorize(fn["title"], fn.get("description", "")),
                            complexity_score=cx.overall, complexity_level=complexity_level(cx.overall),
                            effort_fp=eff.function_points, effort_person_days=eff.person_days,
                            effort_level=eff.level, effort_breakdown=eff.breakdown,
                            target_module=_assign_module(fn["title"], fn.get("description", ""), _categorize(fn["title"], fn.get("description", ""))))
        db.add(func)
        db.flush()
        functions.append(func)

    from app.risk_forecast import forecast_risks
    func_dicts = [{"title": f.title, "description": f.description, "code": f.code} for f in functions]
    forecast = forecast_risks(func_dicts)
    risk = RiskAssessment(session_id=session.id, overall_risk_score=forecast.overall_risk_score, level=forecast.level,
                          schedule_buffer_days=forecast.schedule_buffer_days, summary=forecast.summary,
                          risk_items=[{"category": r.category, "description": r.description, "severity": r.severity, "level": r.level, "mitigation": r.mitigation} for r in forecast.items])
    db.add(risk)
    session.status = "analyzed"

    db.commit()
    results["steps"].append({"step": "functions_decomposed", "count": len(functions), "total_effort_days": round(sum(f.effort_person_days for f in functions), 1)})
    results["steps"].append({"step": "risk_forecast", "level": forecast.level, "score": forecast.overall_risk_score, "buffer_days": forecast.schedule_buffer_days})

    # Step 4: Ready for deliberation
    high_complexity = [f for f in functions if f.complexity_level in ("complex", "very_complex")]
    results["steps"].append({"step": "deliberation_ready", "high_complexity_count": len(high_complexity), "recommendation": "Start deliberation for high-complexity functions" if high_complexity else "All functions within manageable complexity"})

    results["session_id"] = session.id
    results["summary"] = f"Golden flow complete: {len(req_items[:10])} requirements, {len(functions)} functions, {round(sum(f.effort_person_days for f in functions), 1)} person-days, risk: {forecast.level}"
    return results


# ═══════════════════════════════════════════════════════════
# R2 Storage endpoints
# ═══════════════════════════════════════════════════════════

@router.get("/storage/upload-url")
def get_upload_url(
    slug: str,
    filename: str = "file",
    category: str = "source-documents",
    user: User = Depends(get_current_user),
):
    """Get a pre-signed R2 upload URL."""
    if not is_available():
        raise HTTPException(status_code=503, detail="R2 storage not configured")
    key = build_object_key(slug, category, filename)
    result = generate_upload_url(key)
    if not result or "error" in result:
        raise HTTPException(status_code=500, detail=result.get("error", "Upload URL generation failed"))
    return result


@router.get("/storage/download-url")
def get_download_url(
    slug: str,
    object_key: str,
    user: User = Depends(get_current_user),
):
    """Get a pre-signed R2 download URL."""
    if not is_available():
        raise HTTPException(status_code=503, detail="R2 storage not configured")
    result = generate_download_url(object_key)
    if not result or "error" in result:
        raise HTTPException(status_code=500, detail=result.get("error", "Download URL generation failed"))
    return result


@router.get("/storage/status")
def storage_status(
    slug: str,
    user: User = Depends(get_current_user),
):
    """Check R2 storage availability."""
    return {"available": is_available(), "bucket": R2_BUCKET_NAME if is_available() else None}
