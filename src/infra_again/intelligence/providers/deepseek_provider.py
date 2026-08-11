"""DeepSeek Architecture Reasoning Provider.

M4-D: DeepSeek cloud expert behind ArchitectureReasoningProvider protocol.
Uses the official DeepSeek OpenAI-compatible API endpoint.
Never called directly from AGAINPILOT business logic — only through the router.
"""

from __future__ import annotations

import json, os, time, hashlib, urllib.request, urllib.error
from typing import Any

from infra_again.intelligence.providers.openai_provider import TokenUsage
import infra_again.intelligence.model_router as mr


# ═══════════════════════════════════════════════════════════════════
# Configuration — resolved from env, not hard-coded
# ═══════════════════════════════════════════════════════════════════

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"


def _resolve_deepseek_model() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")


def _resolve_deepseek_api_key() -> str | None:
    return os.environ.get("DEEPSEEK_API_KEY")


def _dummy_detected_req():
    from infra_again.intelligence.againpilot import DetectedRequirement
    return DetectedRequirement(
        provider="AWS", platform="KUBERNETES", expected_load="MODERATE",
        availability=[], compliance=[], security=[], data_sensitivity=[],
    )


# ═══════════════════════════════════════════════════════════════════
# DeepSeek Provider
# ═══════════════════════════════════════════════════════════════════

class DeepSeekArchitectureProvider:
    """DeepSeek cloud reasoning provider (OpenAI-compatible API).

    Implements ArchitectureReasoningProvider protocol.
    All outputs go through AGAINPILOT validators — no bypass.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self._model = model or _resolve_deepseek_model()
        self._api_key = api_key or _resolve_deepseek_api_key()
        self._last_usage: TokenUsage | None = None
        # HTTP status code only (never the response body, never the key) —
        # lets callers distinguish "DeepSeek rejected the request" (401/404/
        # 400) from "the request never got a response" (network timeout),
        # which the generic *_TIMEOUT result string previously collapsed
        # into one indistinguishable failure mode.
        self._last_error_code: int | None = None

    def __repr__(self) -> str:
        return f"DeepSeekArchitectureProvider(model={self._model!r}, has_key={bool(self._api_key)})"

    @property
    def role(self) -> mr.ModelRole:
        return mr.ModelRole.CLOUD_EXPERT

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "DEEPSEEK"

    @property
    def last_usage(self) -> TokenUsage | None:
        return self._last_usage

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _failure_result(self, default: str) -> str:
        """Distinguish 'DeepSeek rejected the request' (HTTP 4xx/5xx — bad
        key, bad model, bad request) from a genuine network timeout. Status
        code only, never the response body."""
        if self._last_error_code:
            return f"{default.rsplit('_', 1)[0]}_HTTP_{self._last_error_code}"
        return default

    # ── Internal: call DeepSeek ──────────────────────────────────

    def _chat(self, system_prompt: str, user_message: str, max_tokens: int = 2048,
              temperature: float = 0.3, timeout: int = 90) -> tuple[str | None, TokenUsage]:
        """Call DeepSeek Chat Completions (OpenAI-compatible)."""
        if not self._api_key:
            return None, TokenUsage(provider="DEEPSEEK")

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
            DEEPSEEK_BASE_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        self._last_error_code = None
        last_error = None
        for attempt in range(3):
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                msg = data["choices"][0]["message"]
                # deepseek-v4-pro is a reasoning model: output may be in
                # reasoning_content, content, or both. Prefer content,
                # fall back to reasoning_content.
                content = msg.get("content") or msg.get("reasoning_content") or ""
                usage_info = data.get("usage", {})
                usage = TokenUsage(
                    input_tokens=usage_info.get("prompt_tokens", 0),
                    output_tokens=usage_info.get("completion_tokens", 0),
                    model=self._model,
                    provider="DEEPSEEK",
                )
                self._last_usage = usage
                return content, usage
            except urllib.error.HTTPError as e:
                last_error = e
                self._last_error_code = e.code
                body_text = ""
                try:
                    body_text = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
                if e.code == 429 and attempt < 2:
                    if "insufficient" in body_text.lower() or "credit" in body_text.lower():
                        break  # billing — don't retry
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_error = e
                break
        self._last_usage = TokenUsage(model=self._model, provider="DEEPSEEK")
        return None, self._last_usage

    def _parse_json(self, raw: str | None) -> dict | None:
        """Extract JSON from LLM output, stripping markdown fences."""
        if not raw:
            return None
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
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
        from infra_again.intelligence.againpilot import ARCHITECTURE_INTENT_PROMPT
        content, _ = self._chat(
            ARCHITECTURE_INTENT_PROMPT,
            f"Architecture Brief:\n{brief}\n\nProvider: {provider_pref}\nPlatform: {platform_pref}",
            max_tokens=1024, timeout=60,
        )
        return self._parse_json(content)

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str,
                              req: Any) -> tuple[Any | None, dict]:
        """Two-stage generation via DeepSeek. Returns (proposal, metadata)."""
        from infra_again.intelligence.againpilot import (
            ARCHITECTURE_INTENT_PROMPT, ARCHITECTURE_PROPOSAL_PROMPT,
            _filter_catalog, _build_proposal_from_compact, _validate_proposal,
        )

        meta = {"result": "CLOUD_UNAVAILABLE", "provider": "DEEPSEEK", "model": self._model}
        if not self.is_available():
            return None, meta

        t0 = time.time()

        # Stage 1: ArchitectureIntent
        intent_raw, usage1 = self._chat(
            ARCHITECTURE_INTENT_PROMPT,
            f"Architecture Brief:\n{brief}\n\nProvider: {provider_pref}\nPlatform: {platform_pref}",
            max_tokens=4096, timeout=120,
        )
        meta["stage1Ms"] = int((time.time() - t0) * 1000)
        if self._last_usage:
            meta["usage"] = self._last_usage.to_dict()

        if not intent_raw:
            meta["result"] = self._failure_result("STAGE1_TIMEOUT")
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
            max_tokens=8192, timeout=120,
        )
        meta["stage2Ms"] = int((time.time() - t1) * 1000)
        if self._last_usage:
            meta["usage"] = self._last_usage.to_dict()

        if not prop_raw:
            meta["result"] = self._failure_result("STAGE2_TIMEOUT")
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
            return None, meta
        if completeness.overall.value == "FAIL":
            meta["result"] = "CLOUD_COMPLETENESS_FAIL"
            return None, meta

        meta["result"] = "REAL_LLM"
        meta["qualityResult"] = quality.overall.value
        meta["completenessResult"] = completeness.overall.value
        return proposal, meta

    def refine_architecture(self, nodes: list[dict], edges: list[dict],
                            instruction: str, provider: str,
                            base_req: Any | None = None) -> tuple[Any | None, dict]:
        """Delta-based refine via DeepSeek."""
        from infra_again.intelligence.againpilot import (
            REFINE_DELTA_PROMPT, _compact_current_architecture,
            _apply_refine_delta, _validate_proposal, _merge_refine_requirements,
        )

        meta = {"result": "CLOUD_UNAVAILABLE", "provider": "DEEPSEEK", "model": self._model}
        if not self.is_available():
            return None, meta

        compact = _compact_current_architecture(nodes, edges)
        prompt = (f"CURRENT ARCHITECTURE:\n{json.dumps(compact, indent=2)}\n\n"
                  f"PROVIDER: {provider}\n\n"
                  f"INSTRUCTION: {instruction}\n\n"
                  f"Return the delta JSON per the rules above.")

        content, _ = self._chat(REFINE_DELTA_PROMPT, prompt, max_tokens=8192, timeout=120)
        if self._last_usage:
            meta["usage"] = self._last_usage.to_dict()

        if not content:
            meta["result"] = self._failure_result("CLOUD_TIMEOUT")
            return None, meta

        delta_dict = self._parse_json(content)
        if not delta_dict:
            meta["result"] = "CLOUD_INVALID_JSON"
            return None, meta

        try:
            proposal, delta_obj = _apply_refine_delta(
                nodes, edges, delta_dict,
                req=base_req or _dummy_detected_req(),
                provider=provider,
                generation_provider="DEEPSEEK", generation_model=self._model,
            )
        except Exception:
            meta["result"] = "CLOUD_DELTA_APPLY_FAILED"
            return None, meta

        merged_req = _merge_refine_requirements(base_req, instruction)
        quality, completeness = _validate_proposal(proposal, provider, merged_req)
        # Deterministic validator output only — gate/result/detail come from
        # our own QualityReport/CompletenessReport, never from the model's
        # response. No reasoning_content, no raw provider payload, ever.
        meta["qualityResult"] = quality.overall.value
        meta["completenessResult"] = completeness.overall.value
        if quality.overall.value == "FAIL":
            meta["result"] = "CLOUD_QUALITY_FAIL"
            meta["qualityFailures"] = [
                {"gate": c["gate"], "result": c["result"], "detail": c["detail"]}
                for c in quality.checks if c["result"] == "FAIL"
            ]
            return None, meta
        if completeness.overall.value == "FAIL":
            meta["result"] = "CLOUD_COMPLETENESS_FAIL"
            meta["missingRoles"] = list(completeness.missing_roles)
            return None, meta

        meta["result"] = "REAL_LLM_REFINE"
        return (proposal, delta_obj), meta

    def explain(self, nodes: list[dict], edges: list[dict], provider: str) -> str | None:
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
            "Explain this cloud architecture concisely. Services, layout, security, availability.",
            f"Provider: {provider}\nNodes:\n{node_text}\n\nEdges:\n{edge_text}",
            max_tokens=1024, timeout=30,
        )
        return content
