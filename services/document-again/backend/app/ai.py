"""OIDA AI consultation runtime (AI-ready, human-led).

Provider abstraction + grounded context + independent consultation + honest
no-key fallback. External providers are NOT_CONFIGURED until real credentials
are supplied; the deterministic grounded analyzer and an optional local LLM
(Ollama) keep the Suggestion loop functional without external keys.

AI remembers and suggests. The human decides.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Provider registry (configuration lives in environment or the local settings
# file — never in project data). Models are NOT fixed: the model list is read
# from the provider source at runtime.
# ---------------------------------------------------------------------------

SETTINGS_DIR = Path(os.environ.get("OIDA_AI_SETTINGS_DIR") or Path(__file__).resolve().parent.parent / "data")
SETTINGS_FILE = SETTINGS_DIR / "ai_settings.json"


def _load_settings() -> dict:
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_settings(settings: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
    try:
        SETTINGS_FILE.chmod(0o600)
    except OSError:
        pass


def _provider_by_id(provider_id: str) -> dict | None:
    return next((p for p in PROVIDERS if p["id"] == provider_id), None)

PROVIDERS = [
    {
        "id": "deepseek", "label": "DeepSeek", "env": "DEEPSEEK_API_KEY",
        "base_env": "DEEPSEEK_BASE_URL", "default_base": "https://api.deepseek.com",
        "models_path": "/models", "auth_style": "bearer",
        "external": True, "runtime": "HTTP", "capabilities": ["general reasoning"],
    },
    {
        "id": "gemini", "label": "Gemini", "env": "GEMINI_API_KEY",
        "base_env": "GEMINI_BASE_URL", "default_base": "https://generativelanguage.googleapis.com",
        "models_path": "/v1beta/models", "auth_style": "query",
        "external": True, "runtime": "HTTP", "capabilities": ["general reasoning"],
    },
    {
        "id": "openai", "label": "OpenAI / GPT", "env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE_URL", "default_base": "https://api.openai.com/v1",
        "models_path": "/models", "auth_style": "bearer",
        "external": True, "runtime": "HTTP", "capabilities": ["general reasoning"],
    },
    {
        "id": "codex", "label": "Codex", "env": None,
        "external": False, "runtime": "DEVELOPMENT_ONLY",
        "capabilities": ["code / contract / integration review"],
    },
    {
        "id": "local", "label": "Local LLM", "env": "LOCAL_LLM_BASE_URL",
        "base_env": "LOCAL_LLM_BASE_URL", "default_base": "http://localhost:11434",
        "model_env": "LOCAL_LLM_MODEL", "default_model": "llama3.1:8b",
        "models_path": "/api/tags", "auth_style": "none",
        "external": False, "runtime": "HTTP (Ollama)", "capabilities": ["general / private analysis"],
    },
]


def _stored_settings_for(provider_id: str) -> dict:
    return _load_settings().get(provider_id) or {}


def _key_for(p: dict) -> str | None:
    """Stored settings file wins; environment is the fallback."""
    stored = _stored_settings_for(p["id"]).get("api_key")
    if stored:
        return stored
    return os.environ.get(p["env"]) if p.get("env") else None


def _model_for(p: dict) -> str | None:
    stored = _stored_settings_for(p["id"]).get("model")
    if stored:
        return stored
    if p.get("model_env"):
        return os.environ.get(p["model_env"]) or p.get("default_model")
    return None


def _base_for(p: dict) -> str:
    stored = _stored_settings_for(p["id"]).get("base_url")
    if stored:
        return stored
    return os.environ.get(p.get("base_env")) or p["default_base"]


def provider_status() -> list[dict]:
    out = []
    for p in PROVIDERS:
        if p["id"] == "codex":
            out.append({
                "provider_id": p["id"], "display_name": p["label"],
                "configured": False, "status": "NOT_AVAILABLE",
                "runtime": p["runtime"], "capabilities": p["capabilities"],
                "external": p["external"],
                "note": "Development/review agent only; no stable OIDA runtime interface.",
            })
            continue
        key = _key_for(p)
        configured = bool(key)
        if p["id"] == "local":
            base = _base_for(p)
            model = _model_for(p) or "llama3.1:8b"
            out.append({
                "provider_id": p["id"], "display_name": p["label"],
                "configured": configured,
                "status": "AVAILABLE" if _local_available(base, model) else ("CONFIGURED" if configured else "NOT_CONFIGURED"),
                "endpoint": base, "model": model, "runtime": p["runtime"],
                "capabilities": p["capabilities"], "external": p["external"],
            })
        else:
            model = _model_for(p)
            out.append({
                "provider_id": p["id"], "display_name": p["label"],
                "configured": configured, "status": "CONFIGURED" if configured else "NOT_CONFIGURED",
                "endpoint": _base_for(p), "model": model,
                "runtime": p["runtime"], "capabilities": p["capabilities"],
                "external": p["external"],
            })
    return out


def get_provider_settings(provider_id: str) -> dict:
    p = _provider_by_id(provider_id)
    if not p:
        raise KeyError("Unknown provider")
    stored = _stored_settings_for(provider_id)
    return {
        "provider_id": p["id"],
        "display_name": p["label"],
        "has_api_key": bool(_key_for(p)),
        "model": _model_for(p),
        "base_url": _base_for(p),
        "runtime": p["runtime"],
        "external": p["external"],
    }


def update_provider_settings(provider_id: str, *, api_key: str | None = None, model: str | None = None, base_url: str | None = None) -> dict:
    """Persist a provider's API key / selected model / base URL to the local
    settings file. The key is written to disk (mode 0600) and NEVER returned."""
    p = _provider_by_id(provider_id)
    if not p:
        raise KeyError("Unknown provider")
    settings = _load_settings()
    entry = dict(settings.get(provider_id) or {})
    if api_key is not None:
        entry["api_key"] = api_key
    if model is not None:
        entry["model"] = model
    if base_url is not None:
        entry["base_url"] = base_url
    settings[provider_id] = entry
    _save_settings(settings)
    return get_provider_settings(provider_id)


def list_provider_models(provider_id: str, api_key: str | None = None) -> dict:
    """Read the model list from the provider source (NOT a hard-coded list).

    ``api_key`` may be supplied by the caller (e.g. a key just typed in the UI
    but not yet saved); otherwise the stored/configured key is used."""
    p = _provider_by_id(provider_id)
    if not p:
        raise KeyError("Unknown provider")
    if p["id"] == "codex":
        return {"provider_id": provider_id, "models": [], "source": "NONE", "note": "No model list for Codex."}

    base = _base_for(p).rstrip("/")
    key = api_key or _key_for(p)
    path = p.get("models_path") or "/models"
    needs_key = p["id"] != "local"
    if needs_key and not key:
        return {
            "provider_id": provider_id, "models": [], "source": base + path,
            "error": "API key required — enter and save the key first, then load models.",
        }

    try:
        if p["auth_style"] == "bearer":
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            r = httpx.get(base + path, headers=headers, timeout=15.0)
        elif p["auth_style"] == "query":
            r = httpx.get(base + path, params={"key": key} if key else {}, timeout=15.0)
        else:  # none (local Ollama)
            r = httpx.get(base + path, timeout=15.0)
    except Exception as exc:
        return {"provider_id": provider_id, "models": [], "source": base + path, "error": f"unreachable: {exc}"}

    if r.status_code != 200:
        return {"provider_id": provider_id, "models": [], "source": base + path, "error": f"HTTP {r.status_code}", "hint": r.text[:200]}

    # OpenAI-compatible: {"data": [{"id": "..."}]}
    # Gemini: {"models": [{"name": "models/..."}]}
    # Ollama: {"models": [{"name": "..."}]}
    body = r.json()
    data = body.get("data")
    if data:
        return {"provider_id": provider_id, "models": [m.get("id") for m in data if m.get("id")], "source": base + path}
    models = body.get("models") or []
    if models and isinstance(models[0], dict):
        return {"provider_id": provider_id, "models": [m.get("name") for m in models if m.get("name")], "source": base + path}
    return {"provider_id": provider_id, "models": [m for m in models if isinstance(m, str)], "source": base + path}


def test_provider(provider_id: str) -> dict:
    """Perform a real, minimal round-trip against the configured provider with
    the stored key + selected model, so "Test" reflects actual reachability
    and credential validity — never a placeholder."""
    p = _provider_by_id(provider_id)
    if not p:
        raise KeyError("Unknown provider")
    if p["id"] == "codex":
        return {"provider_id": provider_id, "test": "NOT_APPLICABLE", "reason": "Codex has no OIDA runtime."}

    key = _key_for(p)
    model = _model_for(p)
    if not model:
        return {"provider_id": provider_id, "test": "NO_MODEL", "reason": "Select a model first."}

    if p["id"] == "local":
        base = _base_for(p).rstrip("/")
        ok = _local_available(base, model)
        if not ok:
            return {"provider_id": provider_id, "test": "UNAVAILABLE", "reason": f"Model {model!r} not served by {base}"}
        reply = _local_generate(base, model, "Reply with exactly: OK")
        if not reply:
            return {"provider_id": provider_id, "test": "FAILED", "reason": "No response from local LLM"}
        return {"provider_id": provider_id, "test": "OK", "model": model, "sample": reply[:120]}

    if not key:
        return {"provider_id": provider_id, "test": "NOT_CONFIGURED", "reason": "No API key saved"}

    base = _base_for(p).rstrip("/")
    try:
        if p["id"] == "gemini":
            model_name = model.replace("models/", "", 1) if model.startswith("models/") else model
            r = httpx.post(
                f"{base}/v1beta/models/{model_name}:generateContent",
                params={"key": key},
                json={"contents": [{"parts": [{"text": "Reply with exactly: OK"}]}]},
                timeout=20.0,
            )
        else:  # openai-compatible (deepseek / openai)
            chat_path = "/chat/completions"
            if not base.endswith("/v1"):
                chat_path = "/v1/chat/completions" if p["id"] == "openai" else "/chat/completions"
            r = httpx.post(
                base + chat_path,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": [{"role": "user", "content": "Reply with exactly: OK"}], "max_tokens": 8},
                timeout=20.0,
            )
    except httpx.TimeoutException:
        return {"provider_id": provider_id, "test": "TIMEOUT", "reason": "Provider did not respond in time"}
    except Exception as exc:
        return {"provider_id": provider_id, "test": "ERROR", "reason": str(exc)[:200]}

    if r.status_code == 401:
        return {"provider_id": provider_id, "test": "AUTH_FAILED", "reason": "Invalid API key"}
    if r.status_code == 403:
        return {"provider_id": provider_id, "test": "AUTH_FAILED", "reason": "API key not authorized for this model"}
    if r.status_code == 429:
        return {"provider_id": provider_id, "test": "RATE_LIMITED", "reason": "Rate limited — try again shortly"}
    if r.status_code != 200:
        return {"provider_id": provider_id, "test": "ERROR", "reason": f"HTTP {r.status_code}: {r.text[:160]}"}

    try:
        body = r.json()
        if p["id"] == "gemini":
            text = body["candidates"][0]["content"]["parts"][0].get("text", "")
        else:
            text = body["choices"][0]["message"].get("content", "")
        return {"provider_id": provider_id, "test": "OK", "model": model, "sample": text[:120]}
    except Exception:
        return {"provider_id": provider_id, "test": "OK", "model": model, "sample": "(no text in response)"}


def _local_available(base: str, model: str) -> bool:
    try:
        r = httpx.get(f"{base.rstrip('/')}/api/tags", timeout=1.5)
        if r.status_code != 200:
            return False
        return model in r.text
    except Exception:
        return False


def _local_generate(base: str, model: str, prompt: str) -> str | None:
    try:
        r = httpx.post(
            f"{base.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        return (r.json().get("response") or "").strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Grounded context (bounded, redacts nothing needed here but keeps it scoped)
# ---------------------------------------------------------------------------

def grounded_context(db, project_id: str) -> dict:
    from . import models as m
    from sqlalchemy import select

    project = db.get(m.Project, project_id)
    reqs = db.execute(select(m.Requirement).where(m.Requirement.project_id == project_id)).scalars().all()
    clarifications = db.execute(select(m.Clarification).where(m.Clarification.project_id == project_id)).scalars().all()
    assumptions = db.execute(select(m.Assumption).where(m.Assumption.project_id == project_id)).scalars().all()
    decisions = db.execute(select(m.Decision).where(m.Decision.project_id == project_id)).scalars().all()
    traces = db.execute(select(m.TraceLink).where(m.TraceLink.project_id == project_id)).scalars().all()
    baselines = db.execute(select(m.Baseline).where(m.Baseline.project_id == project_id)).scalars().all()
    crs = db.execute(select(m.ChangeRequest).where(m.ChangeRequest.project_id == project_id)).scalars().all()

    return {
        "project": {"name": project.name, "key": project.key, "description": project.description} if project else None,
        "requirements": [{"code": r.code, "title": r.title, "priority": r.priority, "source_reference": r.source_reference} for r in reqs],
        "clarifications": [{"id": c.semantic_id, "question": c.question, "answer": c.answer, "resolved": c.resolved} for c in clarifications],
        "assumptions": [{"id": a.semantic_id, "content": a.content} for a in assumptions],
        "decisions": [{"id": d.semantic_id, "title": d.title, "content": d.content} for d in decisions],
        "trace_edges": len(traces),
        "baselines": [b.name for b in baselines],
        "change_requests": [c.code for c in crs],
    }


# ---------------------------------------------------------------------------
# Deterministic grounded analyzer (no-key fallback; grounded in project truth)
# ---------------------------------------------------------------------------

def _heuristic_findings(db, project_id: str, ctx: dict) -> list[dict]:
    findings: list[dict] = []
    memory_text = " ".join(
        (c.get("question") or "") + " " + (c.get("answer") or "") for c in ctx["clarifications"]
    ) + " " + " ".join(a["content"] for a in ctx["assumptions"]) + " " + " ".join(
        (d.get("content") or "") for d in ctx["decisions"]
    )

    for r in ctx["requirements"]:
        text = f"{r['title']} {r.get('source_reference') or ''}".lower()
        # Connectivity / bandwidth concern (grounded in a real requirement).
        if re.search(r"connectiv|direct connect|bandwidth", text) and "bandwidth" not in memory_text.lower():
            findings.append({
                "type": "CLARIFICATION_REQUIRED",
                "domain": "requirement",
                "related_object_id": r["code"],
                "title": "Direct Connect bandwidth is not specified.",
                "description": f"{r['code']} covers connectivity, but the available bandwidth is not recorded.",
                "why_it_matters": "Migration throughput and pilot duration may depend on the available bandwidth.",
                "question": "What Direct Connect bandwidth should be used for the migration?",
                "suggested_action": "Record the bandwidth as a clarification and add it as an assumption on the connectivity requirement.",
                "severity": "HIGH",
            })
        # Source not recorded.
        if not r.get("source_reference") and "source not recorded" not in memory_text.lower():
            findings.append({
                "type": "MISSING_INFORMATION",
                "domain": "requirement",
                "related_object_id": r["code"],
                "title": f"Source for {r['code']} is not recorded.",
                "description": f"{r['code']} has no source reference.",
                "why_it_matters": "Tracing the requirement back to the customer request/SOW is needed for change impact and sign-off.",
                "question": "Which customer document or request is this requirement derived from?",
                "suggested_action": "Record the source reference on the requirement.",
                "severity": "LOW",
            })

    # Surface existing OPEN clarifications as answerable suggestions.
    for c in ctx["clarifications"]:
        if not c.get("resolved") and not c.get("answer"):
            q = c["question"] or ""
            if not q:
                continue
            findings.append({
                "type": "CLARIFICATION_REQUIRED",
                "domain": "requirement",
                "related_object_id": c["id"],
                "clarification_id": c["id"],
                "title": _title_from_question(q),
                "description": f"Open clarification: {q}",
                "why_it_matters": "This information is needed for design, execution or acceptance.",
                "question": q,
                "suggested_action": "Answer this clarification so OIDA can record it as project memory.",
                "severity": "MEDIUM",
            })

    # Untraced domains (grounded in the trace graph).
    from .services import _unknown_areas
    has_edges = ctx["trace_edges"] > 0
    for u in _unknown_areas(db, project_id, has_edges):
        findings.append({
            "type": "MISSING_INFORMATION",
            "domain": "infra" if "infra" in (u.get("domain") or "") else ("qa" if "qa" in (u.get("domain") or "") else "project"),
            "related_object_id": None,
            "title": u["label"],
            "description": u["reason"],
            "why_it_matters": "Impact analysis cannot claim completeness where trace coverage is incomplete.",
            "question": f"Should {u['label']} be traced into this project?",
            "suggested_action": "Add trace links or external references for this domain.",
            "severity": "MEDIUM",
        })

    return findings


def _title_from_question(q: str) -> str:
    t = (q or "").strip()
    if t.lower().startswith("what "):
        t = t[5:]
    t = t.rstrip("?").strip()
    if t:
        t = t[0].upper() + t[1:]
    return t or q


# ---------------------------------------------------------------------------
# Consultation (independent runs where available; honest no-key behavior)
# ---------------------------------------------------------------------------

def consult(db, project_id: str, purpose: str = "GENERAL_CONSULTATION", mode: str = "STANDARD") -> dict:
    ctx = grounded_context(db, project_id)
    statuses = {p["provider_id"]: p for p in provider_status()}

    runs: list[dict] = []
    local = statuses.get("local")
    # Independent runs. External providers are NOT_CONFIGURED until keys exist.
    if local and local.get("status") == "AVAILABLE":
        prompt = _build_prompt(ctx, purpose)
        out = _local_generate(local["endpoint"], local["model"], prompt)
        runs.append({
            "provider": "local", "model": local["model"], "status": "COMPLETE" if out else "FAILED",
            "output": (out or "")[:2000], "confidence": None,
        })
    else:
        runs.append({
            "provider": "local", "model": local.get("model") if local else None,
            "status": local.get("status", "NOT_CONFIGURED"), "output": None, "confidence": None,
        })

    findings = _heuristic_findings(db, project_id, ctx)
    coverage = len([r for r in runs if r["status"] == "COMPLETE"])
    requested = len(PROVIDERS)
    available = len([p for p in statuses.values() if p.get("status") in ("AVAILABLE", "CONFIGURED", "COMPLETE")])

    return {
        "purpose": purpose,
        "mode": mode,
        "providers_requested": requested,
        "providers_available": available,
        "runs": runs,
        "coverage": f"{coverage} / {len(runs)} local perspective(s)",
        "findings": findings,
        "confidence": "MEDIUM" if findings else "UNKNOWN",
        "grounded_in": {
            "requirements": len(ctx["requirements"]),
            "trace_edges": ctx["trace_edges"],
            "baselines": ctx["baselines"],
        },
    }


def _build_prompt(ctx: dict, purpose: str) -> str:
    return (
        f"You are OIDA, a project consultant. Purpose: {purpose}.\n"
        "Review this project context and identify concrete missing information, "
        "ambiguities, assumptions to confirm, and risks. Be concise and specific; "
        "only raise concerns grounded in the data below.\n\n"
        f"Project: {ctx['project']}\n"
        f"Requirements: {ctx['requirements']}\n"
        f"Clarifications: {ctx['clarifications']}\n"
        f"Assumptions: {ctx['assumptions']}\n"
        f"Decisions: {ctx['decisions']}\n"
        f"Trace edges: {ctx['trace_edges']}\n"
        "Respond with a short bullet list of concerns, each as: concern | why it matters | question."
    )


# ---------------------------------------------------------------------------
# Answer interpretation (deterministic + optional local; confidence honest)
# ---------------------------------------------------------------------------

def interpret_answer(answer: str, suggestion_title: str, ctx: dict | None = None) -> dict:
    answer = (answer or "").strip()
    interpretation = f"The answer ({answer[:200]}) was recorded."
    confidence = "LOW"
    follow_up = None
    proposed = None

    m = re.search(r"(\d+(?:\.\d+)?)\s*(Gbps|Mbps|GB|TB|hours|days|ms)", answer, re.IGNORECASE)
    if m:
        value, unit = m.groups()
        interpretation = f"{suggestion_title[:120]} is confirmed as {value} {unit}."
        confidence = "MEDIUM"
        proposed = {
            "kind": "assumption",
            "text": f"{suggestion_title[:120]} {value} {unit}.",
            "resolve_clarification": True,
            "requires_impact_analysis": False,
            "note": "Draft-only: creates an assumption; does not modify confirmed requirements or baselines.",
        }
        if re.search(r"dedicated|shared", answer, re.IGNORECASE):
            confidence = "HIGH"
        else:
            follow_up = "Is this capacity dedicated to migration traffic or shared with production workloads?"
    else:
        confidence = "LOW"
        follow_up = "Please specify the value and unit (e.g. 10 Gbps)."
        proposed = {"kind": "clarification", "text": answer[:200], "resolve_clarification": False}

    return {"interpretation": interpretation, "confidence": confidence, "follow_up": follow_up, "proposed_update": proposed}
