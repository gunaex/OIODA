"""
Conductor Again — Intake & Decomposition Router
Parse raw input → decompose into function list → analyze complexity/similarity/effort/risk → distribute.
"""

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.complexity import analyze_complexity, complexity_level
from app.database import get_master_db, get_project_db
from app.effort import estimate_effort
from app.models import (
    FunctionItem,
    IntakeSession,
    RiskAssessment,
    SimilarityPair,
    User,
)
from app.risk_forecast import forecast_risks
from app.similarity import analyze_similarity

router = APIRouter(prefix="/api/{slug}/intake", tags=["intake"])


# ═══════════════════════════════════════════════════════════
# Parse & Decompose
# ═══════════════════════════════════════════════════════════

@router.post("/parse")
def parse_and_decompose(
    slug: str,
    body: dict,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    """Intake raw text → decompose into function list with full analysis."""
    content = body.get("content", "")
    source_type = body.get("source_type", "text")
    source_name = body.get("source_name", "")

    if not content.strip():
        raise HTTPException(status_code=400, detail="Content is required")

    # 1. Create intake session
    session = IntakeSession(
        source_type=source_type,
        source_name=source_name,
        raw_content=content[:10000],
        created_by=user.email,
    )
    db.add(session)
    db.flush()

    # 2. Decompose into functions
    functions_raw = _decompose_text(content)
    functions: list[FunctionItem] = []
    for i, fn in enumerate(functions_raw):
        code = f"F-{i + 1:03d}"
        func = FunctionItem(
            session_id=session.id,
            code=code,
            title=fn["title"],
            description=fn.get("description", ""),
            category=fn.get("category", _categorize(fn["title"], fn.get("description", ""))),
        )
        db.add(func)
        db.flush()
        functions.append(func)

    # 3. Analyze each function
    for func in functions:
        cx = analyze_complexity(func.title, func.description)
        func.complexity_score = cx.overall
        func.complexity_level = complexity_level(cx.overall)
        func.complexity_breakdown = {
            "structural": cx.structural, "domain": cx.domain,
            "integration": cx.integration, "data": cx.data, "uncertainty": cx.uncertainty,
        }

        eff = estimate_effort(func.title, func.description, cx.overall)
        func.effort_fp = eff.function_points
        func.effort_person_days = eff.person_days
        func.effort_level = eff.level
        func.effort_breakdown = eff.breakdown
        func.target_module = _assign_module(func.title, func.description, func.category)

    # 4. Similarity analysis (pairwise)
    similarity_pairs = []
    for i in range(len(functions)):
        for j in range(i + 1, len(functions)):
            sim = analyze_similarity(
                functions[i].title, functions[i].description,
                functions[j].title, functions[j].description,
            )
            if sim.level != "none":
                pair = SimilarityPair(
                    session_id=session.id,
                    function_a_id=functions[i].id,
                    function_b_id=functions[j].id,
                    score=sim.score,
                    level=sim.level,
                    shared_keywords=sim.shared_keywords,
                    recommendation=sim.recommendation,
                )
                db.add(pair)
                similarity_pairs.append(pair)

    # 5. Risk forecast
    func_dicts = [{"title": f.title, "description": f.description, "code": f.code} for f in functions]
    forecast = forecast_risks(func_dicts)
    risk = RiskAssessment(
        session_id=session.id,
        overall_risk_score=forecast.overall_risk_score,
        level=forecast.level,
        schedule_buffer_days=forecast.schedule_buffer_days,
        summary=forecast.summary,
        risk_items=[{
            "category": r.category, "description": r.description,
            "probability": r.probability, "impact": r.impact,
            "severity": r.severity, "level": r.level,
            "mitigation": r.mitigation,
            "affected_functions": r.affected_functions,
        } for r in forecast.items],
    )
    db.add(risk)

    session.status = "analyzed"
    db.commit()

    # Build response
    return {
        "session_id": session.id,
        "source_type": source_type,
        "function_count": len(functions),
        "functions": [
            {
                "id": f.id, "code": f.code, "title": f.title,
                "description": f.description[:200], "category": f.category,
                "complexity": {"score": f.complexity_score, "level": f.complexity_level, "breakdown": f.complexity_breakdown},
                "effort": {"function_points": f.effort_fp, "person_days": f.effort_person_days, "level": f.effort_level, "breakdown": f.effort_breakdown},
                "target_module": f.target_module,
            }
            for f in functions
        ],
        "similarities": [
            {"function_a": sp.function_a_id, "function_b": sp.function_b_id,
             "score": sp.score, "level": sp.level, "recommendation": sp.recommendation}
            for sp in similarity_pairs
        ],
        "risk_forecast": {
            "overall_score": forecast.overall_risk_score,
            "level": forecast.level,
            "schedule_buffer_days": forecast.schedule_buffer_days,
            "summary": forecast.summary,
            "items": [{"category": r.category, "level": r.level, "severity": r.severity, "mitigation": r.mitigation[:100]} for r in forecast.items],
        },
        "total_effort_person_days": round(sum(f.effort_person_days for f in functions), 1),
        "complexity_distribution": {
            level: sum(1 for f in functions if f.complexity_level == level)
            for level in ["trivial", "simple", "moderate", "complex", "very_complex"]
        },
    }


# ═══════════════════════════════════════════════════════════
# Query
# ═══════════════════════════════════════════════════════════

@router.get("/sessions")
def list_sessions(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    sessions = db.query(IntakeSession).order_by(IntakeSession.created_at.desc()).limit(20).all()
    return [
        {
            "id": s.id, "source_type": s.source_type, "source_name": s.source_name,
            "status": s.status, "created_by": s.created_by,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "function_count": db.query(FunctionItem).filter(FunctionItem.session_id == s.id).count(),
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
def get_session(
    slug: str,
    session_id: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    session = db.query(IntakeSession).filter(IntakeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    functions = db.query(FunctionItem).filter(FunctionItem.session_id == session_id).order_by(FunctionItem.code).all()
    similarities = db.query(SimilarityPair).filter(SimilarityPair.session_id == session_id).all()
    risk = db.query(RiskAssessment).filter(RiskAssessment.session_id == session_id).first()

    return {
        "session": {
            "id": session.id, "source_type": session.source_type, "source_name": session.source_name,
            "status": session.status, "raw_content": session.raw_content[:500],
            "created_at": session.created_at.isoformat() if session.created_at else None,
        },
        "functions": [
            {
                "id": f.id, "code": f.code, "title": f.title, "description": f.description,
                "category": f.category, "complexity_score": f.complexity_score,
                "complexity_level": f.complexity_level, "complexity_breakdown": f.complexity_breakdown,
                "effort_fp": f.effort_fp, "effort_person_days": f.effort_person_days,
                "effort_level": f.effort_level, "effort_breakdown": f.effort_breakdown,
                "target_module": f.target_module, "priority": f.priority, "status": f.status,
            }
            for f in functions
        ],
        "similarities": [
            {"id": s.id, "function_a_id": s.function_a_id, "function_b_id": s.function_b_id,
             "score": s.score, "level": s.level, "recommendation": s.recommendation}
            for s in similarities
        ],
        "risk": {
            "overall_score": risk.overall_risk_score, "level": risk.level,
            "schedule_buffer_days": risk.schedule_buffer_days, "summary": risk.summary,
            "items": risk.risk_items,
        } if risk else None,
    }


# ═══════════════════════════════════════════════════════════
# Text Decomposition Engine
# ═══════════════════════════════════════════════════════════

def _decompose_text(text: str) -> list[dict]:
    """Break free-text into structured function items."""
    functions = []

    # Strategy 1: Look for numbered/bulleted items
    lines = text.strip().split("\n")
    current_title = None
    current_desc = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect numbered/bulleted list items
        match = re.match(r'^[\s]*([\d]+[\.\)]\s*|[-*•]\s*|\[\d+\]\s*)(.+)', line)
        if match:
            if current_title:
                functions.append({"title": current_title, "description": " ".join(current_desc)})
            current_title = match.group(2).strip()
            current_desc = []
        elif current_title:
            current_desc.append(line)

    if current_title:
        functions.append({"title": current_title, "description": " ".join(current_desc)})

    # Strategy 2: If no structured list found, split by sentences/paragraphs
    if not functions:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for p in paragraphs:
            # Take first sentence as title
            sentences = re.split(r'(?<=[.!?])\s+', p)
            title = sentences[0] if sentences else p[:100]
            desc = " ".join(sentences[1:]) if len(sentences) > 1 else ""
            functions.append({"title": title[:200], "description": desc[:500]})

    # Strategy 3: If still too few, split long paragraphs
    if len(functions) < 2 and len(text) > 200:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        functions = []
        for i, s in enumerate(sentences):
            if len(s.strip()) > 20:
                functions.append({"title": s.strip()[:200], "description": ""})

    return functions[:30]  # Cap at 30


def _categorize(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if any(w in text for w in ["ui", "page", "screen", "display", "button", "form", "dashboard", "modal", "table"]):
        return "ui"
    if any(w in text for w in ["api", "endpoint", "service", "backend", "server", "database", "query", "schema"]):
        return "backend"
    if any(w in text for w in ["integration", "connect", "sync", "import", "export", "webhook", "adapter"]):
        return "integration"
    if any(w in text for w in ["data", "migration", "etl", "report", "analytics", "warehouse"]):
        return "data"
    if any(w in text for w in ["auth", "login", "password", "role", "permission", "security", "encrypt"]):
        return "security"
    if any(w in text for w in ["report", "pdf", "export", "dashboard", "chart", "graph"]):
        return "reporting"
    return "feature"


def _assign_module(title: str, description: str, category: str) -> str:
    text = f"{title} {description}".lower()
    if category in ("data", "reporting"):
        return "DEV"
    if any(w in text for w in ["test", "qa", "quality", "verify", "validate", "check"]):
        return "QA_AGAIN"
    if any(w in text for w in ["plan", "schedule", "milestone", "resource", "assign", "track"]):
        return "PM_AGAIN"
    if any(w in text for w in ["requirement", "vision", "skill", "govern", "policy", "decide"]):
        return "CONDUCTOR"
    return "DEV"
