"""OpenAI Architecture Reasoning Provider.

M4: Real cloud expert behind ArchitectureReasoningProvider protocol.
Never called directly from AGAINPILOT business logic — only through the router.
"""

from __future__ import annotations

import json, os, time, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field

import infra_again.intelligence.model_router as mr


# ═══════════════════════════════════════════════════════════════════
# Configuration — resolved from env, not hard-coded
# ═══════════════════════════════════════════════════════════════════

def _resolve_openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o")


def _resolve_openai_api_key() -> str | None:
    """Read API key from env. Never log, never persist, never expose to frontend."""
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("AGAINPILOT_CLOUD_API_KEY")


# ═══════════════════════════════════════════════════════════════════
# Token usage record
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = "OPENAI"

    def to_dict(self) -> dict:
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "model": self.model,
            "provider": self.provider,
        }


# ═══════════════════════════════════════════════════════════════════
# OpenAI Provider
# ═══════════════════════════════════════════════════════════════════

class OpenAIArchitectureProvider:
    """OpenAI cloud reasoning provider.

    Implements ArchitectureReasoningProvider protocol.
    All outputs go through AGAINPILOT validators — no bypass.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self._model = model or _resolve_openai_model()
        self._api_key = api_key or _resolve_openai_api_key()
        self._last_usage: TokenUsage | None = None

    def __repr__(self) -> str:
        return f"OpenAIArchitectureProvider(model={self._model!r}, has_key={bool(self._api_key)})"

    @property
    def role(self) -> mr.ModelRole:
        return mr.ModelRole.CLOUD_EXPERT

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "OPENAI"

    @property
    def last_usage(self) -> TokenUsage | None:
        return self._last_usage

    def is_available(self) -> bool:
        return bool(self._api_key)

    # ── Internal: call OpenAI ────────────────────────────────────

    def _chat(self, system_prompt: str, user_message: str, max_tokens: int = 2048,
              temperature: float = 0.3, timeout: int = 90) -> tuple[str | None, TokenUsage]:
        """Call OpenAI Chat Completions. Returns (content, usage)."""
        if not self._api_key:
            return None, TokenUsage()

        body = json.dumps({
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        t0 = time.time()
        last_error = None
        for attempt in range(3):
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                content = data["choices"][0]["message"]["content"]
                usage_info = data.get("usage", {})
                usage = TokenUsage(
                    input_tokens=usage_info.get("prompt_tokens", 0),
                    output_tokens=usage_info.get("completion_tokens", 0),
                    model=self._model,
                    provider="OPENAI",
                )
                self._last_usage = usage
                return content, usage
            except urllib.error.HTTPError as e:
                last_error = e
                body_text = ""
                try:
                    body_text = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
                if e.code == 429 and attempt < 2:
                    # Check if it's rate limit vs credit exhaustion
                    if "insufficient_quota" in body_text or "credit_balance_exhausted" in body_text:
                        # Not retryable — no credits
                        break
                    time.sleep(2 * (attempt + 1))
                    continue
                # Log the error detail in the result
                self._last_error_detail = body_text
                break
            except Exception as e:
                last_error = e
                break
        self._last_usage = TokenUsage(model=self._model, provider="OPENAI")
        return None, self._last_usage

    def _parse_json(self, raw: str | None) -> dict | None:
        """Extract JSON from LLM output, stripping markdown fences."""
        if not raw:
            return None
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first fence line (```json or ```)
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last fence line
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            import re
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            return None

    # ── Protocol methods ──────────────────────────────────────────

    def generate_intent(self, brief: str, provider_pref: str, platform_pref: str) -> dict | None:
        from infra_again.intelligence.againpilot import ARCHITECTURE_INTENT_PROMPT  # type: ignore
        content, _ = self._chat(
            ARCHITECTURE_INTENT_PROMPT,
            f"Architecture Brief:\n{brief}\n\nProvider: {provider_pref}\nPlatform: {platform_pref}",
            max_tokens=1024, timeout=60,
        )
        return self._parse_json(content)

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str,
                              req: Any) -> tuple[Any | None, dict]:
        """Two-stage generation via OpenAI. Returns (proposal, metadata)."""
        from infra_again.intelligence.againpilot import (  # type: ignore
            ARCHITECTURE_INTENT_PROMPT, ARCHITECTURE_PROPOSAL_PROMPT,
            _parse_json as ap_parse_json, _filter_catalog,
            _build_proposal_from_compact, _validate_proposal,
            DetectedRequirement,
        )

        meta = {"result": "CLOUD_UNAVAILABLE", "provider": "OPENAI", "model": self._model}
        if not self.is_available():
            return None, meta

        t0 = time.time()

        # Stage 1: ArchitectureIntent
        intent_raw, usage1 = self._chat(
            ARCHITECTURE_INTENT_PROMPT,
            f"Architecture Brief:\n{brief}\n\nProvider: {provider_pref}\nPlatform: {platform_pref}",
            max_tokens=1024, timeout=60,
        )
        meta["stage1Ms"] = int((time.time() - t0) * 1000)
        meta["usage"] = self._last_usage.to_dict() if self._last_usage else {}

        if not intent_raw:
            meta["result"] = "STAGE1_TIMEOUT"
            return None, meta

        intent = self._parse_json(intent_raw)
        if not intent:
            meta["result"] = "STAGE1_INVALID_JSON"
            return None, meta

        # Filter catalog
        try:
            components = intent.get("components", [])
            filtered = _filter_catalog(provider_pref, components)
        except Exception:
            filtered = ""

        # Stage 2: ArchitectureProposal
        t1 = time.time()
        prop_raw, usage2 = self._chat(
            ARCHITECTURE_PROPOSAL_PROMPT,
            f"Architecture Intent: {json.dumps(intent)}\n\nFiltered Service Catalog ({provider_pref}):\n{filtered}",
            max_tokens=2048, timeout=90,
        )
        meta["stage2Ms"] = int((time.time() - t1) * 1000)

        # Merge usage
        if self._last_usage:
            meta["usage"] = self._last_usage.to_dict()

        if not prop_raw:
            meta["result"] = "STAGE2_TIMEOUT"
            return None, meta

        compact = self._parse_json(prop_raw)
        if not compact:
            meta["result"] = "STAGE2_INVALID_JSON"
            return None, meta

        brief_hash = hashlib.sha256(brief.encode()).hexdigest()[:12]
        proposal = _build_proposal_from_compact(
            compact, req, provider_pref, self._model,
            meta.get("stage1Ms", 0), meta.get("stage2Ms", 0), brief_hash,
        )
        if not proposal:
            meta["result"] = "BUILD_FAILED"
            return None, meta

        # Validate — cloud output NEVER bypasses quality/completeness gates
        quality, completeness = _validate_proposal(proposal, provider_pref, req)
        if quality.overall.value == "FAIL":
            meta["result"] = "CLOUD_QUALITY_FAIL"
            meta["qualityFailures"] = [c for c in quality.checks if c["result"] == "FAIL"]
            return None, meta
        if completeness.overall.value == "FAIL":
            meta["result"] = "CLOUD_COMPLETENESS_FAIL"
            meta["missingRoles"] = completeness.missing_roles
            return None, meta

        meta["result"] = "REAL_LLM"
        meta["qualityResult"] = quality.overall.value
        meta["completenessResult"] = completeness.overall.value
        return proposal, meta

    def refine_architecture(self, nodes: list[dict], edges: list[dict],
                            instruction: str, provider: str,
                            base_req: Any | None = None) -> tuple[Any | None, dict]:
        """Delta-based refine via OpenAI."""
        from infra_again.intelligence.againpilot import (  # type: ignore
            REFINE_DELTA_PROMPT, _compact_current_architecture,
            _apply_refine_delta, _validate_proposal, DetectedRequirement,
            AgainPilotProposal, RefineDelta, GeneratedNode, GeneratedEdge,
            _derive_views, _merge_refine_requirements,
        )

        def _dummy_req() -> DetectedRequirement:
            return DetectedRequirement(
                provider="AWS", platform="KUBERNETES", expected_load="MODERATE",
                availability=[], compliance=[], security=[], data_sensitivity=[],
            )

        meta = {"result": "CLOUD_UNAVAILABLE", "provider": "OPENAI", "model": self._model}
        if not self.is_available():
            return None, meta

        compact = _compact_current_architecture(nodes, edges)
        prompt = (f"CURRENT ARCHITECTURE:\n{json.dumps(compact, indent=2)}\n\n"
                  f"PROVIDER: {provider}\n\n"
                  f"INSTRUCTION: {instruction}\n\n"
                  f"Return the delta JSON per the rules above.")

        content, _ = self._chat(REFINE_DELTA_PROMPT, prompt, max_tokens=2048, timeout=90)

        if self._last_usage:
            meta["usage"] = self._last_usage.to_dict()

        if not content:
            meta["result"] = "CLOUD_TIMEOUT"
            return None, meta

        delta_dict = self._parse_json(content)
        if not delta_dict:
            meta["result"] = "CLOUD_INVALID_JSON"
            return None, meta

        # Apply delta to get new proposal
        try:
            proposal, delta_obj = _apply_refine_delta(
                nodes, edges, delta_dict,
                req=base_req or _dummy_req(),
                provider=provider,
                generation_provider="OPENAI", generation_model=self._model,
            )
        except Exception:
            meta["result"] = "CLOUD_DELTA_APPLY_FAILED"
            return None, meta

        # Validate — cloud refine NEVER bypasses governance
        merged_req = _merge_refine_requirements(base_req, instruction)
        quality, completeness = _validate_proposal(proposal, provider, merged_req)
        if quality.overall.value == "FAIL":
            meta["result"] = "CLOUD_QUALITY_FAIL"
            meta["qualityFailures"] = [c for c in quality.checks if c["result"] == "FAIL"]
            return None, meta
        if completeness.overall.value == "FAIL":
            meta["result"] = "CLOUD_COMPLETENESS_FAIL"
            meta["missingRoles"] = completeness.missing_roles
            return None, meta

        meta["result"] = "REAL_LLM_REFINE"
        meta["qualityResult"] = quality.overall.value
        meta["completenessResult"] = completeness.overall.value
        return (proposal, delta_obj), meta

    def explain(self, nodes: list[dict], edges: list[dict], provider: str) -> str | None:
        """Explain architecture via OpenAI."""
        if not self.is_available():
            return None
        node_text = "\n".join([
            f"- {n.get('name','?')} ({n.get('category','?')}) [{n.get('nativeService','')}]"
            for n in nodes[:20]
        ])
        edge_text = "\n".join([
            f"- {e.get('sourceNodeId','?')} → {e.get('targetNodeId','?')} [{e.get('type','?')}: {e.get('label','')}]"
            for e in edges[:20]
        ])
        content, _ = self._chat(
            "Explain this cloud architecture concisely. Services, layout, security, availability. No chain-of-thought.",
            f"Provider: {provider}\nNodes:\n{node_text}\n\nEdges:\n{edge_text}",
            max_tokens=1024, timeout=30,
        )
        return content

    def security_analysis(self, nodes: list[dict], edges: list[dict],
                          req: Any) -> dict | None:
        """Security analysis via OpenAI."""
        if not self.is_available():
            return None
        content, _ = self._chat(
            "Analyze this cloud architecture for security issues. Return JSON with findings.",
            json.dumps({"nodes": nodes[:30], "edges": edges[:30]}, default=str),
            max_tokens=1024, timeout=60,
        )
        return self._parse_json(content)
