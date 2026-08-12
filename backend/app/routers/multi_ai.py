"""
Conductor Again — Multi-AI Parallel Analysis Router
Sends vision/requirements to multiple AI models independently,
then synthesizes with a different model.

E8.1-F: in ECOSYSTEM_MODE (default), every AI call in this router routes through
LocalAIControlCenterClient.execute_capability() — the AIExecutionGateway — instead of
directly instantiating a provider adapter with a decrypted AIAccount.api_key_encrypted.
Panel "diversity" is now diversity of local Ollama model family (LACC's only wired
executor today, disclosed) rather than diversity of cloud provider account, since
Conductor no longer selects or holds provider credentials itself. The pre-E8.1
direct-adapter path remains available ONLY when ECOSYSTEM_MODE=false (LEGACY_DIRECT_AI_MODE,
dev-only, disclosed, §34) — it is never reachable in ecosystem mode.
"""

import asyncio
import os
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.adapters.base import AIRequest
from app.auth import get_current_user, require_roles
from app.database import get_master_db, get_project_db
from app.integration.lacc_client import LocalAIControlCenterClient
from app.models import AIResource, User

router = APIRouter(prefix="/api/{slug}/multi-ai", tags=["multi-ai"])

ECOSYSTEM_MODE = os.getenv("ECOSYSTEM_MODE", "false").lower() == "true"

# Local Ollama model families used for panel diversity in ecosystem mode — chosen for
# genuinely different model lineages (not just quantization variants of one base model),
# preserving the original feature's intent (independent reasoning from different model
# families) without Conductor selecting a cloud provider/credential itself.
LOCAL_DIVERSITY_MODELS = ["qwen2.5:7b", "llama3.1:8b", "gemma3:4b", "qwen2.5-coder:7b"]


async def _call_one_capability_slot(
    slot_index: int, prompt: str, system_instruction: str, correlation_id: str,
) -> dict:
    """Ecosystem-mode panel member: routes through the AIExecutionGateway."""
    model = LOCAL_DIVERSITY_MODELS[slot_index % len(LOCAL_DIVERSITY_MODELS)]
    full_prompt = f"{system_instruction}\n\n{prompt}"
    t0 = time.monotonic()
    result = await asyncio.to_thread(
        LocalAIControlCenterClient.execute_capability,
        capability="BUSINESS_ANALYSIS",
        correlation_id=correlation_id,
        prompt=full_prompt,
        model_preference=model,
        request_id=f"req-multiai-{uuid.uuid4().hex[:8]}",
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    if result.get("status") != "COMPLETED":
        return {
            "provider": "ollama", "model": model,
            "error": result.get("outputSummary", "AI execution failed")[:300],
            "content": None, "tokens": {}, "latency_ms": elapsed,
        }
    return {
        "provider": result.get("providerUsed", "ollama"), "model": result.get("modelUsed", model),
        "content": result.get("outputSummary"), "tokens": {}, "latency_ms": elapsed,
        "finish_reason": "stop",
    }


async def _call_one_resource(
    resource: AIResource,
    prompt: str,
    system_instruction: str,
) -> dict:
    """LEGACY_DIRECT_AI_MODE path (dev-only, ECOSYSTEM_MODE=false). Not reachable in
    ecosystem mode — see _call_one_capability_slot for the AIExecutionGateway path."""
    account = resource.account
    if not account or not account.api_key_encrypted:
        return {
            "provider": account.provider.code if account and account.provider else "unknown",
            "model": "N/A",
            "error": "No API key configured",
            "content": None,
            "tokens": {},
            "latency_ms": 0,
        }

    from app.routers.ai_resources import _decrypt
    api_key = _decrypt(account.api_key_encrypted)
    provider_code = account.provider.code if account.provider else "unknown"
    model_id = resource.model.model_id if resource.model else "default"

    adapter = get_adapter(provider_code, api_key)
    if not adapter:
        return {
            "provider": provider_code,
            "model": model_id,
            "error": f"No adapter for {provider_code}",
            "content": None,
            "tokens": {},
            "latency_ms": 0,
        }

    try:
        t0 = time.monotonic()
        response = await adapter.chat(AIRequest(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            model_id=model_id,
            max_tokens=2000,
            temperature=0.5,
        ))
        elapsed = int((time.monotonic() - t0) * 1000)
        return {
            "provider": provider_code,
            "model": response.model_used or model_id,
            "content": response.content,
            "tokens": {
                "input": response.input_tokens,
                "output": response.output_tokens,
            },
            "latency_ms": elapsed,
            "finish_reason": response.finish_reason,
        }
    except Exception as e:
        return {
            "provider": provider_code,
            "model": model_id,
            "error": str(e)[:300],
            "content": None,
            "tokens": {},
            "latency_ms": 0,
        }


@router.post("/analyze")
async def multi_ai_analyze(
    slug: str,
    body: dict,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor", "approver")),
):
    """
    Send vision/requirement to MULTIPLE AI models in parallel,
    then optionally synthesize with a different model.

    Body:
    {
        "content": "Build a BOM system...",
        "mode": "vision" | "requirement",
        "panel_size": 3,           // how many AIs to use
        "synthesize": true          // run a second-pass synthesis
    }
    """
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content required")

    mode = body.get("mode", "requirement")
    panel_size = min(body.get("panel_size", 3), 5)
    synthesize = body.get("synthesize", True)

    # ── System instruction based on mode ──────────────────
    if mode == "vision":
        system_instruction = """You are a senior business analyst and solution architect. Analyze the following Business Vision carefully.

Provide your analysis in a structured format:

## Key Objectives
- What are the top 3-5 business goals?

## Domain Insights
- What domain-specific knowledge is important here?

## Missing Information
- What critical information is missing or ambiguous?

## Clarification Questions
- What 3-5 questions would you ask to clarify?

## Risks & Constraints
- What are the key risks and constraints?

## Recommended Approach
- What technical approach would you recommend?"""
    else:
        system_instruction = """You are a senior requirements engineer. Analyze the following requirement(s) carefully.

Provide your analysis in a structured format:

## Completeness Assessment
- Are the requirements complete? What's missing?

## Ambiguity Detection
- What parts are ambiguous or open to interpretation?

## Technical Feasibility
- Are there technical concerns?

## Dependencies
- What external dependencies exist?

## Testability
- How would you verify each requirement?

## Suggested Improvements
- What would you add, remove, or change?"""

    prompt = f"""Please analyze the following {'Business Vision' if mode == 'vision' else 'Requirements'}:

{content[:8000]}

Provide a thorough, independent analysis. Think for yourself — do not assume what others might say."""

    correlation_id = f"corr-multiai-{uuid.uuid4().hex[:12]}"

    if ECOSYSTEM_MODE:
        # AIExecutionGateway path — no AIResource/api_key_encrypted lookup at all.
        tasks = [
            _call_one_capability_slot(i, prompt, system_instruction, correlation_id)
            for i in range(panel_size)
        ]
        results = await asyncio.gather(*tasks)
        selected = None  # no AIResource objects in this mode; _run_synthesis branches on this
    else:
        # ── LEGACY_DIRECT_AI_MODE: select diverse AI resources with actual API keys ──
        resources = master_db.query(AIResource).filter(
            AIResource.enabled == True,
            AIResource.health_state.in_(["AVAILABLE", "DEGRADED"]),
        ).all()

        valid_resources = [r for r in resources if r.account and r.account.api_key_encrypted]
        if not valid_resources:
            raise HTTPException(status_code=400, detail="No AI resources with API keys available")

        seen_providers = set()
        selected = []
        for r in sorted(valid_resources, key=lambda r: r.base_priority, reverse=True):
            pcode = r.account.provider.code if r.account and r.account.provider else "unknown"
            if pcode not in seen_providers:
                selected.append(r)
                seen_providers.add(pcode)
            if len(selected) >= panel_size:
                break
        if len(selected) < panel_size:
            for r in valid_resources:
                if r.id not in {s.id for s in selected}:
                    selected.append(r)
                if len(selected) >= panel_size:
                    break

        tasks = [_call_one_resource(r, prompt, system_instruction) for r in selected[:panel_size]]
        results = await asyncio.gather(*tasks)

    panel = [
        {
            "provider": r["provider"],
            "model": r["model"],
            "content": r["content"],
            "tokens": r.get("tokens", {}),
            "latency_ms": r.get("latency_ms", 0),
            "error": r.get("error"),
        }
        for r in results
    ]

    # ── Synthesis pass (different model if available) ─────
    synthesis = None
    if synthesize and len(panel) >= 2:
        synthesis = await _run_synthesis(
            master_db, selected, content, panel, mode, system_instruction, correlation_id,
        )

    return {
        "mode": mode,
        "panel_size": len(panel),
        "panel": panel,
        "synthesis": synthesis,
    }


async def _run_synthesis(
    master_db: Session,
    original_panel,
    content: str,
    panel_results: list[dict],
    mode: str,
    system_instruction: str,
    correlation_id: str = "",
) -> dict | None:
    """Run a second-pass synthesis using a different model than the panel.
    `original_panel` is None in ECOSYSTEM_MODE (no AIResource objects involved)."""
    if ECOSYSTEM_MODE or original_panel is None:
        return await _run_synthesis_via_gateway(content, panel_results, mode, correlation_id)

    # ── LEGACY_DIRECT_AI_MODE ──
    panel_providers = set()
    for p in original_panel:
        pcode = p.account.provider.code if p.account and p.account.provider else ""
        panel_providers.add(pcode)

    # Find a resource from a different provider
    synth_resource = None
    all_resources = master_db.query(AIResource).filter(
        AIResource.enabled == True,
        AIResource.health_state.in_(["AVAILABLE", "DEGRADED"]),
    ).all()

    for r in all_resources:
        pcode = r.account.provider.code if r.account and r.account.provider else ""
        if pcode not in panel_providers:
            synth_resource = r
            break

    # If no different provider, use any unused one
    if not synth_resource:
        for r in all_resources:
            if r.id not in {p.id for p in original_panel}:
                synth_resource = r
                break

    if not synth_resource:
        return None  # No synthesizer available

    account = synth_resource.account
    if not account or not account.api_key_encrypted:
        return None

    from app.routers.ai_resources import _decrypt
    api_key = _decrypt(account.api_key_encrypted)
    provider_code = account.provider.code if account.provider else "unknown"
    model_id = synth_resource.model.model_id if synth_resource.model else "default"

    adapter = get_adapter(provider_code, api_key)
    if not adapter:
        return None

    # Build synthesis prompt from all panel results
    analyses_text = ""
    for i, p in enumerate(panel_results):
        label = chr(65 + i)  # A, B, C...
        content_text = p.get("content", p.get("error", "No response"))[:2000]
        analyses_text += f"\n### Analyst {label} ({p['provider']}/{p['model']})\n{content_text}\n"

    synth_prompt = f"""You are the SYNTHESIZER. Below are independent analyses from {len(panel_results)} different AI models analyzing the same {'Business Vision' if mode == 'vision' else 'Requirements'}.

Original content:
{content[:1000]}

{analyses_text}

Your job:
1. Identify where all analysts AGREE (consensus points)
2. Identify where they DISAGREE (divergent views)
3. Highlight unique insights that only ONE analyst caught
4. Produce a UNIFIED RECOMMENDATION

Format your response as:

## Consensus Points
- [List agreements]

## Divergent Views
- [List disagreements with who said what]

## Unique Insights
- [Insights only one analyst caught]

## Unified Recommendation
- [Your synthesized recommendation]

## Confidence
- [High/Medium/Low — with brief justification]"""

    try:
        t0 = time.monotonic()
        response = await adapter.chat(AIRequest(
            messages=[
                {"role": "system", "content": "You are a synthesis expert. Combine multiple independent AI analyses into a unified, balanced assessment."},
                {"role": "user", "content": synth_prompt},
            ],
            model_id=model_id,
            max_tokens=2500,
            temperature=0.3,
        ))
        elapsed = int((time.monotonic() - t0) * 1000)

        return {
            "provider": provider_code,
            "model": response.model_used or model_id,
            "content": response.content,
            "tokens": {
                "input": response.input_tokens,
                "output": response.output_tokens,
            },
            "latency_ms": elapsed,
        }
    except Exception as e:
        return {
            "provider": provider_code,
            "model": model_id,
            "error": str(e)[:300],
            "content": None,
        }


async def _run_synthesis_via_gateway(
    content: str, panel_results: list[dict], mode: str, correlation_id: str,
) -> dict | None:
    """Ecosystem-mode synthesis: routes through the AIExecutionGateway, using a local
    model family distinct from the panel's (same diversity intent as the legacy path,
    without Conductor selecting a cloud provider/credential)."""
    analyses_text = ""
    for i, p in enumerate(panel_results):
        label = chr(65 + i)
        content_text = (p.get("content") or p.get("error") or "No response")[:2000]
        analyses_text += f"\n### Analyst {label} ({p['provider']}/{p['model']})\n{content_text}\n"

    synth_prompt = f"""You are the SYNTHESIZER. Below are independent analyses from {len(panel_results)} different AI models analyzing the same {'Business Vision' if mode == 'vision' else 'Requirements'}.

Original content:
{content[:1000]}

{analyses_text}

Your job:
1. Identify where all analysts AGREE (consensus points)
2. Identify where they DISAGREE (divergent views)
3. Highlight unique insights that only ONE analyst caught
4. Produce a UNIFIED RECOMMENDATION

Format your response as:

## Consensus Points
- [List agreements]

## Divergent Views
- [List disagreements with who said what]

## Unique Insights
- [Insights only one analyst caught]

## Unified Recommendation
- [Your synthesized recommendation]

## Confidence
- [High/Medium/Low — with brief justification]"""

    synth_model = "qwen2.5-coder:7b"  # last diversity slot — distinct from panel slots 0-2
    t0 = time.monotonic()
    result = await asyncio.to_thread(
        LocalAIControlCenterClient.execute_capability,
        capability="BUSINESS_ANALYSIS",
        correlation_id=correlation_id,
        prompt=synth_prompt,
        model_preference=synth_model,
        request_id=f"req-multiai-synth-{uuid.uuid4().hex[:8]}",
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    if result.get("status") != "COMPLETED":
        return {
            "provider": "ollama", "model": synth_model,
            "error": result.get("outputSummary", "Synthesis failed")[:300], "content": None,
        }
    return {
        "provider": result.get("providerUsed", "ollama"), "model": result.get("modelUsed", synth_model),
        "content": result.get("outputSummary"),
        "tokens": {}, "latency_ms": elapsed,
    }
