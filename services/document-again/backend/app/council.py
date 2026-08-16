"""OIDA R15 — Real Multi-Agent Council runtime.

AI-Ready, Human-Led. Independent providers consult on the SAME normalized
question + context envelope with NO peer answers (no cross-contamination),
then a deterministic aggregator organizes perspectives. The human reviews.

Authority split (documented, not assumed):
  OIDA            = UI + consultation request + human review + aggregation surface
  Context Builder = project-grounded context (frontend builds the envelope)
  Document Again  = consultation record (Council consultation is project truth)
  Conductor Again = deeper workflow orchestration / blind-critique deliberation
                    authority (NOT duplicated here — OIDA Council is the
                    human-facing consultation surface, not Conductor's
                    deliberation runtime).
  Provider adapters = model execution (this module)

No keys, no problem: external providers are NOT_CONFIGURED until real
credentials exist. Local Ollama keeps the Council runnable in single-provider
mode. Aggregation is deterministic and keyless; it never decides the project
answer and never treats model agreement as project truth.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from . import ai as ai_runtime

# ---------------------------------------------------------------------------
# Phase 1 — Provider capability registry
# ---------------------------------------------------------------------------

# Per-provider capabilities. These are real, conservative capabilities only.
# Unknown/untested capabilities are false, never guessed.
_PROVIDER_CAPS = {
    "deepseek": {
        "display_name": "DeepSeek", "execution_mode": "API",
        "supports_reasoning": True, "supports_structured_output": True,
        "supports_tools": False, "supports_images": False, "context_limit": None,
    },
    "gemini": {
        "display_name": "Gemini", "execution_mode": "API",
        "supports_reasoning": True, "supports_structured_output": True,
        "supports_tools": False, "supports_images": False, "context_limit": None,
    },
    "openai": {
        "display_name": "GPT", "execution_mode": "API",
        "supports_reasoning": True, "supports_structured_output": True,
        "supports_tools": False, "supports_images": False, "context_limit": None,
    },
    "codex": {
        "display_name": "Codex", "execution_mode": "DEVELOPMENT_ONLY",
        "supports_reasoning": True, "supports_structured_output": False,
        "supports_tools": False, "supports_images": False, "context_limit": None,
    },
    "local": {
        "display_name": "Local LLM", "execution_mode": "LOCAL_API",
        "supports_reasoning": True, "supports_structured_output": False,
        "supports_tools": False, "supports_images": False, "context_limit": None,
    },
}

# Provider run statuses (Phase 7).
RUN_STATUSES = {
    "QUEUED", "RUNNING", "COMPLETED", "FAILED", "TIMED_OUT",
    "NOT_CONFIGURED", "NOT_AVAILABLE", "CANCELLED",
}

# Provider status → run status for providers that never started.
_STATUS_TO_RUN = {
    "AVAILABLE": None, "LOCAL_AVAILABLE": None, "CONFIGURED": None,
    "NOT_CONFIGURED": "NOT_CONFIGURED", "NOT_AVAILABLE": "NOT_AVAILABLE",
    "DEGRADED": None, "ERROR": None, "DISABLED": "DISABLED",
}


def capability_registry() -> list[dict]:
    """Full capability registry (Phase 1). NOT_CONFIGURED is never a failure —
    it is an availability state. The core OIDA system stays operational."""
    statuses = {p["provider_id"]: p for p in ai_runtime.provider_status()}
    out = []
    for p in ai_runtime.PROVIDERS:
        caps = _PROVIDER_CAPS.get(p["id"], {})
        st = statuses.get(p["id"], {})
        status = st.get("status", "NOT_CONFIGURED")
        if p["id"] == "codex":
            status = "NOT_AVAILABLE"
        elif p["id"] == "local":
            status = st.get("status") or "NOT_CONFIGURED"
        else:
            configured = st.get("configured")
            if not configured:
                status = "NOT_CONFIGURED"
            elif status in ("CONFIGURED",):
                status = "AVAILABLE" if st.get("model") else "NOT_CONFIGURED"
        out.append({
            "provider_id": p["id"],
            "display_name": caps.get("display_name", p["label"]),
            "status": status,
            "execution_mode": caps.get("execution_mode"),
            "model": st.get("model"),
            "supports_reasoning": caps.get("supports_reasoning", False),
            "supports_structured_output": caps.get("supports_structured_output", False),
            "supports_tools": caps.get("supports_tools", False),
            "supports_images": caps.get("supports_images", False),
            "context_limit": caps.get("context_limit"),
            "configured": st.get("configured", False),
            "external": p.get("external", False),
            "runtime": p.get("runtime"),
            "note": st.get("note") or (None if status not in ("NOT_CONFIGURED", "NOT_AVAILABLE")
                                      else "No API key configured." if status == "NOT_CONFIGURED"
                                      else "No OIDA runtime interface."),
        })
    return out


def council_mode(registry: list[dict] | None = None) -> dict:
    """No-key safe mode summary (Phase 2)."""
    reg = registry or capability_registry()
    available = [p for p in reg if p["status"] in ("AVAILABLE", "LOCAL_AVAILABLE")]
    return {
        "available_providers": [p["provider_id"] for p in available],
        "available_count": len(available),
        "total_count": len(reg),
        "mode": "MULTI_PROVIDER" if len(available) >= 2 else ("SINGLE_PROVIDER" if len(available) == 1 else "NONE"),
        "label": f"{len(available)} of {len(reg)} providers available",
    }


# ---------------------------------------------------------------------------
# Phase 3 — Agent contract
# ---------------------------------------------------------------------------

def build_agent_contract(
    consultation_id: str, project_id: str, task_type: str, question: str,
    context_envelope: dict, role: str | None = None,
) -> dict:
    """The SAME normalized task contract for every provider. Core project facts
    are never customized per provider (only formatting may differ)."""
    return {
        "consultation_id": consultation_id,
        "project_id": project_id,
        "task_type": task_type,
        "role": role or "GENERAL_REVIEWER",
        "question": question,
        "context_envelope": context_envelope,
        "instructions": {
            "independent_reasoning": True,
            "do_not_assume_missing_facts": True,
            "separate_fact_from_inference": True,
            "cite_authority_sources": True,
            "identify_unknowns": True,
            "do_not_make_project_decisions": True,
            "advisory_only": True,
        },
    }


# ---------------------------------------------------------------------------
# Phase 5 / 6 — system prompt: fact/inference discipline + source citing
# ---------------------------------------------------------------------------

def _system_prompt(task_type: str, role: str, source_hint: str) -> str:
    return (
        "You are an independent consultant in an AI-Ready, Human-Led project workspace. "
        f"Task type: {task_type}. Role: {role}.\n"
        "\n"
        "You are a consultant, reviewer and challenger. You are NOT a project, document, "
        "PM, QA, Infra or commercial authority. You do not make project decisions.\n"
        "\n"
        "REASON INDEPENDENTLY. You have NOT seen and must NOT assume any other model's answer.\n"
        "\n"
        "STRICT FACT/INFERENCE DISCIPLINE — label every statement with exactly one basis:\n"
        "  FACT            — directly recorded in the provided context\n"
        "  ASSUMPTION      — you are treating something unrecorded as true\n"
        "  INFERENCE       — you are deriving from facts (may be wrong)\n"
        "  OPINION         — your own judgment\n"
        "  RECOMMENDATION  — a proposed next step (not project truth)\n"
        "  UNKNOWN         — a gap you cannot resolve from the context\n"
        "Never let a recommendation masquerade as project truth. Authority wins over AI consensus.\n"
        "\n"
        "When you can, cite the authority + object id of the facts you rely on. "
        "Do NOT fabricate citations.\n"
        "\n"
        "DO NOT assume facts that are missing from the context. State them as UNKNOWN or "
        "ASSUMPTION instead.\n"
        "\n"
        f"{source_hint}\n"
    )


def _source_hint(envelope: dict, max_facts: int = 60) -> str:
    """A compact, bounded list of citable authority facts (data minimization)."""
    facts = envelope.get("authority_map") or []
    if not facts:
        return "No source facts were provided; cite nothing."
    lines = []
    for f in facts[:max_facts]:
        auth = f.get("authority", "UNKNOWN")
        oid = f.get("source_object_id") or f.get("id") or "-"
        title = (f.get("title") or "")[:80]
        kind = f.get("fact_type", "fact")
        lines.append(f"- [{auth}] {oid} ({kind}): {title}")
    return "AVAILABLE SOURCE FACTS (cite these ids only):\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 4 — normalized agent output
# ---------------------------------------------------------------------------

def _run_id(provider_id: str) -> str:
    return f"run_{provider_id}_{int(time.time() * 1000)}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_run(provider_id: str, model: str | None, status: str, reason: str | None = None) -> dict:
    return {
        "run_id": _run_id(provider_id),
        "provider_id": provider_id,
        "model": model,
        "status": status,
        "summary": "",
        "findings": [],
        "assumptions": [],
        "unknowns": [],
        "questions": [],
        "recommendations": [],
        "disagreements_expected": [],
        "completed_at": _now_iso() if status == "COMPLETED" else None,
        "latency_ms": 0,
        "error": reason,
        "raw": None,
        "structured": False,
    }


def _is_noise_line(line: str) -> bool:
    """Filter instruction-echo / boilerplate lines that some models repeat
    instead of answering (e.g. 'We need answer only JSON object.')."""
    low = line.lower()
    noise_prefixes = (
        "we need", "we must", "we should", "you are", "you must", "you should",
        "respond with", "reply with", "available source facts", "project context",
        "question:", "strict fact", "reason independently",
    )
    if low.startswith(noise_prefixes):
        return True
    if "json object" in low and "findings" in low:
        return True
    if re.fullmatch(r"[^a-z0-9]*(respond|reply|answer)[^a-z0-9]*", low):
        return True
    return False


def _parse_local_lines(text: str) -> list[dict]:
    """Lenient parser for line-format output. Lines matching
    'SEVERITY|TYPE|statement' become structured findings. Long prose and
    narration lines (chain-of-thought echoes) are DROPPED, not turned into
    fake findings. Only short, substantive non-matching lines become UNKNOWN."""
    findings = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        m = re.match(r"^(HIGH|MEDIUM|LOW)\s*[|:/]\s*(RISK|ASSUMPTION|UNKNOWN|QUESTION|RECOMMENDATION|INFERENCE|OPINION|FACT)\s*[|:/-]\s*(.+)$", line, re.IGNORECASE)
        if m:
            severity, ftype, statement = m.groups()
            findings.append({
                "title": statement[:90],
                "statement": statement,
                "finding_type": ftype.upper(),
                "severity": severity.upper(),
                "confidence": "MEDIUM",
                "basis": "INFERENCE" if ftype.upper() in ("RISK", "RECOMMENDATION") else ftype.upper(),
                "source_refs": [],
                "requires_human_review": True,
            })
            continue
        # Non-matching line: keep only short substantive notes, drop narration.
        if len(line) > 160:
            continue
        if _is_noise_line(line):
            continue
        if re.match(r"^(okay|here|first|second|next|also|additionally|to |for |the |this |that |i |we |you |let |need |based|note|however|therefore|thus|finally)\b", line.lower()):
            continue
        findings.append({
            "title": line[:90],
            "statement": line,
            "finding_type": "UNKNOWN",
            "severity": "LOW",
            "confidence": "LOW",
            "basis": "UNKNOWN",
            "source_refs": [],
            "requires_human_review": True,
        })
    return findings


def _parse_structured(text: str) -> list[dict] | None:
    """Attempt strict JSON parse for external structured providers."""
    try:
        data = json.loads(text)
    except Exception:
        # Try to extract a JSON object/array from the text.
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(1))
        except Exception:
            return None
    if isinstance(data, dict):
        data = data.get("findings") or data.get("result") or [data]
    if not isinstance(data, list):
        return None
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ftype = (item.get("finding_type") or item.get("type") or "UNKNOWN").upper()
        basis = (item.get("basis") or ("FACT" if ftype == "FACT" else "INFERENCE")).upper()
        out.append({
            "title": (item.get("title") or item.get("statement") or "")[:90],
            "statement": item.get("statement") or item.get("title") or "",
            "finding_type": ftype,
            "severity": (item.get("severity") or "MEDIUM").upper(),
            "confidence": (item.get("confidence") or "MEDIUM").upper(),
            "basis": basis,
            "source_refs": item.get("source_refs") or [],
            "requires_human_review": bool(item.get("requires_human_review", True)),
        })
    return out or None


def _match_source_refs(text: str, envelope: dict, limit: int = 3) -> list[dict]:
    """Deterministic source-aware citation: attach real envelope facts whose
    keywords overlap the finding text. Never fabricates citations."""
    facts = envelope.get("authority_map") or []
    words = {w for w in re.findall(r"[a-z0-9]{4,}", (text or "").lower())}
    if not words or not facts:
        return []
    hits = []
    for f in facts:
        ftxt = " ".join(str(f.get(k) or "") for k in ("title", "status", "id", "source_object_id")).lower()
        fwords = set(re.findall(r"[a-z0-9]{4,}", ftxt))
        if words & fwords:
            hits.append({
                "authority": f.get("authority", "UNKNOWN"),
                "source_object_id": f.get("source_object_id") or f.get("id"),
                "fact_type": f.get("fact_type"),
            })
    # De-duplicate, preserve order.
    seen, out = set(), []
    for h in hits:
        k = (h["authority"], h["source_object_id"])
        if k not in seen:
            seen.add(k)
            out.append(h)
        if len(out) >= limit:
            break
    return out


def _normalize(provider_id: str, model: str | None, raw: str, envelope: dict) -> dict:
    """Normalize raw model output into the standard Agent Result (Phase 4)."""
    structured = _parse_structured(raw)
    if structured is not None:
        findings = structured
        used_structured = True
    else:
        findings = _parse_local_lines(raw)
        used_structured = False

    for f in findings:
        if not f.get("source_refs"):
            f["source_refs"] = _match_source_refs(
                f"{f.get('title', '')} {f.get('statement', '')}", envelope
            )
        f["requires_human_review"] = f.get("requires_human_review", True)

    parsed_note = None
    if raw and not findings:
        parsed_note = "Provider returned output that did not follow the contract (no findings parsed)."

    def by_type(t):
        return [f for f in findings if f["finding_type"] == t]

    return {
        "run_id": _run_id(provider_id),
        "provider_id": provider_id,
        "model": model,
        "status": "COMPLETED",
        "summary": raw[:400] if raw else "",
        "findings": findings,
        "assumptions": by_type("ASSUMPTION"),
        "unknowns": by_type("UNKNOWN"),
        "questions": by_type("QUESTION"),
        "recommendations": by_type("RECOMMENDATION"),
        "disagreements_expected": [],
        "completed_at": _now_iso(),
        "raw": raw[:4000],
        "structured": used_structured,
        "parsed_note": parsed_note,
    }


# ---------------------------------------------------------------------------
# Provider execution (sync, used inside threads)
# ---------------------------------------------------------------------------

def _chat(provider_id: str, model: str, system: str, user: str, max_tokens: int = 900) -> str:
    """One provider round-trip. Returns text or raises RuntimeError."""
    p = ai_runtime._provider_by_id(provider_id)
    key = ai_runtime._key_for(p) if p else None
    base = (ai_runtime._base_for(p) if p else "").rstrip("/")

    if provider_id == "local":
        base = base or "http://localhost:11434"
        r = httpx.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": f"{system}\n\n{user}", "stream": False},
            timeout=180.0,
        )
        if r.status_code != 200:
            raise RuntimeError(f"local HTTP {r.status_code}")
        return (r.json().get("response") or "").strip()

    if not key:
        raise RuntimeError("NOT_CONFIGURED")

    if provider_id == "gemini":
        model_name = model.replace("models/", "", 1) if model.startswith("models/") else model
        r = httpx.post(
            f"{base}/v1beta/models/{model_name}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}]},
            timeout=90.0,
        )
        if r.status_code != 200:
            raise RuntimeError(f"gemini HTTP {r.status_code}: {r.text[:160]}")
        try:
            return r.json()["candidates"][0]["content"]["parts"][0].get("text", "")
        except Exception:
            return ""

    # openai-compatible (deepseek / openai)
    path = "/v1/chat/completions" if provider_id == "openai" else "/chat/completions"
    if base.endswith("/v1"):
        path = "/chat/completions"
    r = httpx.post(
        base + path,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], "max_tokens": max_tokens},
        timeout=60.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{provider_id} HTTP {r.status_code}: {r.text[:160]}")
    try:
        msg = r.json()["choices"][0]["message"]
        text = msg.get("content") or msg.get("reasoning_content") or ""
        if not text:
            raise RuntimeError("empty response")
        return text
    except Exception as exc:
        raise RuntimeError(f"empty response: {exc}")


def _run_provider_sync(
    provider_id: str, contract: dict, envelope: dict,
) -> dict:
    """Execute one provider against the shared contract (Phase 7). Isolated state;
    no peer answers. Failures are captured, never fatal to the consultation."""
    caps = _PROVIDER_CAPS.get(provider_id, {})
    statuses = {p["provider_id"]: p for p in ai_runtime.provider_status()}
    st = statuses.get(provider_id, {})

    if provider_id == "codex":
        return _empty_run("codex", None, "NOT_AVAILABLE", "Development agent only; no OIDA runtime.")

    model = st.get("model")
    if provider_id == "local":
        model = model or "llama3.1:8b"
        if st.get("status") not in ("AVAILABLE", "LOCAL_AVAILABLE", "CONFIGURED"):
            return _empty_run(provider_id, model, "NOT_AVAILABLE", "Local Ollama not serving this model.")
    else:
        if st.get("status") == "NOT_CONFIGURED" or not st.get("configured"):
            return _empty_run(provider_id, model, "NOT_CONFIGURED", "No API key configured.")
        if not model:
            return _empty_run(provider_id, model, "NOT_CONFIGURED", "No model selected.")

    system = _system_prompt(
        contract["task_type"], contract.get("role"), _source_hint(envelope, max_facts=25),
    )
    context_json = json.dumps(_minimize_envelope(envelope), ensure_ascii=False)[:5000]
    if caps.get("supports_structured_output"):
        user = (
            f"QUESTION:\n{contract['question']}\n\n"
            "PROJECT CONTEXT (normalized, authority-annotated):\n" + context_json + "\n\n"
            "Respond with ONLY a JSON object (no markdown) of the form:\n"
            '{"findings":[{"title":"...","statement":"...","finding_type":"RISK",'
            '"severity":"HIGH","confidence":"MEDIUM","basis":"INFERENCE",'
            '"source_refs":[{"authority":"INFRA_AGAIN","source_object_id":"DESIGN-EBAE25"}]}]}\n'
            "finding_type must be one of RISK, ASSUMPTION, UNKNOWN, QUESTION, RECOMMENDATION.\n"
            "severity must be one of HIGH, MEDIUM, LOW.\n"
            "basis must be one of FACT, ASSUMPTION, INFERENCE, OPINION, RECOMMENDATION, UNKNOWN.\n"
            "source_refs may only cite ids from the available source facts above. "
            "Do not invent facts or citations absent from the context.\n"
            "Output ONLY the JSON object — no preamble, no explanation, no chain-of-thought."
        )
    else:
        user = (
            f"QUESTION:\n{contract['question']}\n\n"
            "PROJECT CONTEXT (normalized, authority-annotated):\n" + context_json + "\n\n"
            "Respond with your independent analysis. List each finding on its own line as "
            "SEVERITY|TYPE|STATEMENT (SEVERITY: HIGH/MEDIUM/LOW; TYPE: RISK/ASSUMPTION/"
            "UNKNOWN/QUESTION/RECOMMENDATION). Do not invent facts absent from the context."
        )
    t0 = time.monotonic()
    try:
        raw = _chat(provider_id, model, system, user)
        elapsed = int((time.monotonic() - t0) * 1000)
        if not raw:
            raise RuntimeError("empty response")
        result = _normalize(provider_id, model, raw, envelope)
        result["latency_ms"] = elapsed
        return result
    except RuntimeError as exc:
        status = "TIMED_OUT" if "timeout" in str(exc).lower() else "FAILED"
        if "NOT_CONFIGURED" in str(exc):
            status = "NOT_CONFIGURED"
        run = _empty_run(provider_id, model, status, str(exc)[:300])
        run["latency_ms"] = int((time.monotonic() - t0) * 1000)
        return run
    except Exception as exc:
        run = _empty_run(provider_id, model, "FAILED", str(exc)[:300])
        run["latency_ms"] = int((time.monotonic() - t0) * 1000)
        return run


def _minimize_envelope(envelope: dict) -> dict:
    """Data-minimized envelope sent to providers (Phase 26): facts only, no
    secrets, no full documents, capped lists."""
    def cap(items, n=40):
        return items[:n] if isinstance(items, list) else items

    return {
        "project": envelope.get("project"),
        "question": envelope.get("question"),
        "requirements": cap(envelope.get("requirements"), 30),
        "clarifications": cap(envelope.get("clarifications"), 20),
        "assumptions": cap(envelope.get("assumptions"), 20),
        "decisions": cap(envelope.get("decisions"), 20),
        "pm_context": {
            "tasks": cap((envelope.get("pm_context") or {}).get("tasks"), 40),
            "effort": (envelope.get("pm_context") or {}).get("effort"),
        },
        "qa_context": {
            "defects": cap((envelope.get("qa_context") or {}).get("defects"), 20),
            "cycles": cap((envelope.get("qa_context") or {}).get("cycles"), 10),
            "coverage": (envelope.get("qa_context") or {}).get("coverage"),
        },
        "infra_context": {
            "note": (envelope.get("infra_context") or {}).get("note"),
            "bound_design": (envelope.get("infra_context") or {}).get("bound_design"),
            "components": cap((envelope.get("infra_context") or {}).get("components"), 40),
            "connections": cap((envelope.get("infra_context") or {}).get("connections"), 40),
        },
        "coverage": envelope.get("coverage"),
        "authority_map": cap(envelope.get("authority_map"), 60),
    }


# ---------------------------------------------------------------------------
# Phase 8 — context snapshot
# ---------------------------------------------------------------------------

def snapshot_hash(envelope: dict) -> str:
    payload = json.dumps(envelope, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_snapshot(envelope: dict, task_type: str, question: str) -> dict:
    cov = envelope.get("authority_coverage") or {}
    return {
        "context_version": envelope.get("context_version") or "1.1",
        "context_hash": snapshot_hash(envelope),
        "built_at": (envelope.get("freshness") or {}).get("built_at") or _now_iso(),
        "authority_coverage": cov,
        "question": question,
        "task_type": task_type,
        "intent": envelope.get("intent"),
    }


# ---------------------------------------------------------------------------
# Phase 10 — deterministic aggregator
# ---------------------------------------------------------------------------

_CLUSTER_STOPWORDS = {
    "high", "medium", "low", "risk", "risks", "assumption", "unknown", "question",
    "recommendation", "inference", "opinion", "fact", "the", "and", "for", "with",
    "this", "that", "from", "was", "are", "not", "has", "have", "will",
}


def _cluster_key(finding: dict) -> str:
    text = " ".join(str(finding.get(k) or "") for k in ("title", "statement")).lower()
    words = sorted({w for w in re.findall(r"[a-z0-9]{4,}", text) if w not in _CLUSTER_STOPWORDS})
    return " ".join(words[:10])


def aggregate_runs(runs: list[dict]) -> dict:
    """Deterministic, keyless aggregator. Organizes perspectives; NEVER decides
    the project answer. Model agreement is NOT project truth."""
    completed = [r for r in runs if r.get("status") == "COMPLETED"]
    clusters: dict[str, list[dict]] = {}

    for r in completed:
        for f in r.get("findings", []):
            key = _cluster_key(f)
            clusters.setdefault(key, []).append({
                "provider_id": r["provider_id"],
                "model": r.get("model"),
                "title": f.get("title"),
                "statement": f.get("statement"),
                "finding_type": f.get("finding_type"),
                "severity": f.get("severity"),
                "confidence": f.get("confidence"),
                "basis": f.get("basis"),
                "source_refs": f.get("source_refs") or [],
                "run_id": r.get("run_id"),
            })

    consensus, disagreements, unique, shared_risks = [], [], [], []
    unknowns, questions, recommendations = [], [], []
    unknown_keys, question_keys = set(), set()

    for key, items in clusters.items():
        n = len(items)
        severities = {i["severity"] for i in items}
        title = items[0]["title"]
        statement = items[0]["statement"]
        basis = items[0]["basis"]
        # merge source refs across providers
        refs, refk = [], set()
        for i in items:
            for s in i["source_refs"]:
                k = (s.get("authority"), s.get("source_object_id"))
                if k not in refk:
                    refk.add(k)
                    refs.append(s)

        entry = {
            "title": title,
            "statement": statement,
            "providers": sorted({i["provider_id"] for i in items}),
            "severities": {p: [i["severity"] for i in items if i["provider_id"] == p][0] for p in sorted({i["provider_id"] for i in items})},
            "basis": basis,
            "source_refs": refs,
            "agreement": n,
            "advisory": True,
            "authority_note": "AI agreement is a consensus recommendation, NOT project truth. Authority records win.",
        }

        if n >= 2:
            if len(severities) > 1:
                disagreements.append({**entry, "kind": "SEVERITY_DISAGREEMENT"})
            else:
                consensus.append(entry)
            if any(i["finding_type"] == "RISK" for i in items):
                shared_risks.append(entry)
        else:
            unique.append(entry)

        for i in items:
            if i["finding_type"] == "UNKNOWN" and (i["statement"] not in unknown_keys):
                unknown_keys.add(i["statement"])
                unknowns.append({"statement": i["statement"], "provider_id": i["provider_id"], "source_refs": i["source_refs"]})
            if i["finding_type"] == "QUESTION" and (i["statement"] not in question_keys):
                question_keys.add(i["statement"])
                questions.append({"question": i["statement"], "provider_id": i["provider_id"], "source_refs": i["source_refs"]})
            if i["finding_type"] == "RECOMMENDATION":
                recommendations.append({"recommendation": i["statement"], "provider_id": i["provider_id"], "severity": i["severity"]})

    mode = "MULTI_PROVIDER" if len(completed) >= 2 else ("SINGLE_PROVIDER" if len(completed) == 1 else "NONE")
    return {
        "aggregation_mode": mode,
        "note": "Deterministic aggregator. It organizes perspectives; it does NOT decide the project answer." if mode != "SINGLE_PROVIDER"
                else "Only one provider completed — SINGLE_PROVIDER mode. This is NOT multi-agent consensus.",
        "completed_providers": [r["provider_id"] for r in completed],
        "consensus": consensus,
        "disagreements": disagreements,
        "unique_insights": unique,
        "shared_risks": shared_risks,
        "unknown_areas": unknowns,
        "questions": questions,
        "recommendations": recommendations,
        "recommended_human_attention": [
            {"item": "Consensus is advisory only; confirm against authority records before acting."}
        ] if consensus else [],
    }


# ---------------------------------------------------------------------------
# Phase 7 — parallel independent execution (public entrypoint)
# ---------------------------------------------------------------------------

async def _gather_runs(contract: dict, envelope: dict, provider_ids: list[str]) -> list[dict]:
    """Concurrent, isolated provider runs. Promise.allSettled-equivalent: one
    failure never fails the consultation."""
    results = await asyncio.gather(
        *[asyncio.to_thread(_run_provider_sync, pid, contract, envelope) for pid in provider_ids],
        return_exceptions=True,
    )
    out = []
    for pid, res in zip(provider_ids, results):
        if isinstance(res, BaseException):
            out.append(_empty_run(pid, None, "FAILED", str(res)[:200]))
        else:
            out.append(res)
    return out


def run_council(
    project_id: str, task_type: str, question: str, context_envelope: dict,
    consultation_id: str, role: str | None = None,
) -> dict:
    """Full independent-run Council execution (sync wrapper)."""
    reg = capability_registry()
    runnable = [p for p in reg if p["status"] in ("AVAILABLE", "LOCAL_AVAILABLE")]
    provider_ids = [p["provider_id"] for p in runnable]

    contract = build_agent_contract(consultation_id, project_id, task_type, question, context_envelope, role)
    snapshot = build_snapshot(context_envelope, task_type, question)

    runs = asyncio.run(_gather_runs(contract, context_envelope, provider_ids))
    # Non-runnable providers still appear as run cards (Phase 16: never hide).
    ran_ids = {r["provider_id"] for r in runs}
    for p in reg:
        if p["provider_id"] not in ran_ids:
            status = p["status"]
            run_status = _STATUS_TO_RUN.get(status, "NOT_AVAILABLE")
            runs.append(_empty_run(
                p["provider_id"], p.get("model"), run_status,
                p.get("note") or ("Not available" if status in ("NOT_CONFIGURED", "NOT_AVAILABLE") else None),
            ))

    aggregation = aggregate_runs(runs)
    return {
        "consultation_id": consultation_id,
        "project_id": project_id,
        "task_type": task_type,
        "role": role or "GENERAL_REVIEWER",
        "question": question,
        "snapshot": snapshot,
        "council_mode": council_mode(reg),
        "runs": runs,
        "aggregation": aggregation,
        "status": "COMPLETED",
    }
