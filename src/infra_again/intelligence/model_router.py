"""AGAINPILOT Hybrid Model Router.

Phase M3: Governed model routing with local-first escalation to cloud.

Roles:
  FAST_LOCAL       — qwen2.5:7b  (intent extraction, classification)
  LOCAL_ARCHITECT  — llama3.1:8b (architecture generation)
  CLOUD_EXPERT     — configurable cloud model

Policies:
  LOCAL_ONLY   — never call cloud
  LOCAL_FIRST  — try local, escalate on failure (default)
  CLOUD_FIRST  — skip local for complex tasks
"""

from __future__ import annotations

import hashlib, json, os, time
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Protocol


# ═══════════════════════════════════════════════════════════════════
# Model Roles
# ═══════════════════════════════════════════════════════════════════

class ModelRole(str, Enum):
    FAST_LOCAL = "FAST_LOCAL"
    LOCAL_ARCHITECT = "LOCAL_ARCHITECT"
    CLOUD_EXPERT = "CLOUD_EXPERT"


# ═══════════════════════════════════════════════════════════════════
# Execution Policies
# ═══════════════════════════════════════════════════════════════════

class ExecutionPolicy(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    LOCAL_FIRST = "LOCAL_FIRST"
    CLOUD_FIRST = "CLOUD_FIRST"


# ═══════════════════════════════════════════════════════════════════
# Result Modes
# ═══════════════════════════════════════════════════════════════════

class FinalResultMode(str, Enum):
    LOCAL_ACCEPTED = "LOCAL_ACCEPTED"
    LOCAL_CORRECTED = "LOCAL_CORRECTED"
    CLOUD_ESCALATED = "CLOUD_ESCALATED"
    CLOUD_DIRECT = "CLOUD_DIRECT"
    BLOCKED = "BLOCKED"
    NEEDS_USER_REVIEW = "NEEDS_USER_REVIEW"


# ═══════════════════════════════════════════════════════════════════
# Escalation Reasons
# ═══════════════════════════════════════════════════════════════════

class EscalationReason(str, Enum):
    LOCAL_MODEL_UNAVAILABLE = "LOCAL_MODEL_UNAVAILABLE"
    LOCAL_TIMEOUT = "LOCAL_TIMEOUT"
    INVALID_STRUCTURED_OUTPUT = "INVALID_STRUCTURED_OUTPUT"
    QUALITY_GATE_FAILED = "QUALITY_GATE_FAILED"
    COMPLETENESS_GATE_FAILED = "COMPLETENESS_GATE_FAILED"
    CORRECTION_FAILED = "CORRECTION_FAILED"
    POLICY_CLOUD_FIRST = "POLICY_CLOUD_FIRST"
    REFINE_COMPLEX_SEMANTIC = "REFINE_COMPLEX_SEMANTIC"
    CLOUD_UNAVAILABLE = "CLOUD_UNAVAILABLE"
    CLOUD_TIMEOUT = "CLOUD_TIMEOUT"
    CLOUD_INVALID_OUTPUT = "CLOUD_INVALID_OUTPUT"
    CLOUD_QUALITY_FAIL = "CLOUD_QUALITY_FAIL"
    CLOUD_COMPLETENESS_FAIL = "CLOUD_COMPLETENESS_FAIL"


# ═══════════════════════════════════════════════════════════════════
# Provenance
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RoutingProvenance:
    """Complete audit trail for a routed request."""
    request_policy: str = ""
    request_type: str = ""  # "generate" | "refine" | "explain" | "security"

    # Local attempt
    local_model: str = ""
    local_result: str = ""
    local_latency_ms: int = 0
    local_correction_used: bool = False
    local_correction_result: str = ""

    # Escalation
    escalated: bool = False
    escalation_reason: str = ""

    # Cloud attempt
    cloud_provider: str = ""
    cloud_model: str = ""
    cloud_result: str = ""
    cloud_latency_ms: int = 0

    # Token / cost observability
    cloud_input_tokens: int = 0
    cloud_output_tokens: int = 0

    # Final
    final_result_mode: str = ""
    generation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    brief_hash: str = ""

    def to_dict(self) -> dict:
        d = {
            "requestPolicy": self.request_policy,
            "requestType": self.request_type,
            "localModel": self.local_model,
            "localResult": self.local_result,
            "localLatencyMs": self.local_latency_ms,
            "localCorrectionUsed": self.local_correction_used,
            "localCorrectionResult": self.local_correction_result,
            "escalated": self.escalated,
            "escalationReason": self.escalation_reason,
            "cloudProvider": self.cloud_provider,
            "cloudModel": self.cloud_model,
            "cloudResult": self.cloud_result,
            "cloudLatencyMs": self.cloud_latency_ms,
            "finalResultMode": self.final_result_mode,
            "generationTimestamp": self.generation_timestamp,
            "briefHash": self.brief_hash,
        }
        if self.cloud_input_tokens or self.cloud_output_tokens:
            d["tokenUsage"] = {
                "inputTokens": self.cloud_input_tokens,
                "outputTokens": self.cloud_output_tokens,
            }
        return d


# ═══════════════════════════════════════════════════════════════════
# Architecture Reasoning Provider Interface
# ═══════════════════════════════════════════════════════════════════

class ArchitectureReasoningProvider(Protocol):
    """Abstract provider for architecture reasoning tasks."""

    @property
    def role(self) -> ModelRole: ...

    @property
    def model_name(self) -> str: ...

    @property
    def provider_name(self) -> str: ...

    def is_available(self) -> bool: ...

    def generate_intent(self, brief: str, provider_pref: str, platform_pref: str) -> dict | None: ...

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str, req: Any) -> tuple[Any | None, dict]: ...

    def refine_architecture(self, nodes: list[dict], edges: list[dict], instruction: str, provider: str, base_req: Any | None) -> tuple[Any | None, dict]: ...


# ═══════════════════════════════════════════════════════════════════
# Local Ollama Provider
# ═══════════════════════════════════════════════════════════════════

class LocalOllamaProvider:
    """Local model provider via Ollama."""

    def __init__(self, model_name: str, role: ModelRole = ModelRole.LOCAL_ARCHITECT):
        self._model = model_name
        self._role = role

    @property
    def role(self) -> ModelRole:
        return self._role

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "LOCAL_LLM"

    def is_available(self) -> bool:
        try:
            import urllib.request, json
            r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
            data = json.loads(r.read())
            return any(self._model.split(":")[0] in m.get("name", "") for m in data.get("models", []))
        except Exception:
            return False

    def generate_intent(self, brief: str, provider_pref: str, platform_pref: str) -> dict | None:
        from .againpilot import _ollama_chat, ARCHITECTURE_INTENT_PROMPT, _parse_json, STAGE1_TIMEOUT
        try:
            raw = _ollama_chat(
                ARCHITECTURE_INTENT_PROMPT,
                f"Architecture Brief:\n{brief}\n\nProvider: {provider_pref}\nPlatform: {platform_pref}",
                max_tokens=1024, timeout=STAGE1_TIMEOUT, model_override=self._model,
            )
            return _parse_json(raw)
        except Exception:
            return None

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str, req: Any) -> tuple[Any | None, dict]:
        from .againpilot import _generate_real_ai, OLLAMA_MODEL as _orig
        import infra_again.intelligence.againpilot as ap
        ap.OLLAMA_MODEL = self._model
        try:
            result = _generate_real_ai(brief, provider_pref, platform_pref, req, provider_pref)
        finally:
            ap.OLLAMA_MODEL = _orig
        return result

    def refine_architecture(self, nodes: list[dict], edges: list[dict], instruction: str, provider: str, base_req: Any | None) -> tuple[Any | None, dict]:
        from .againpilot import _generate_real_refine, OLLAMA_MODEL as _orig
        import infra_again.intelligence.againpilot as ap
        ap.OLLAMA_MODEL = self._model
        try:
            result = _generate_real_refine(nodes, edges, instruction, provider, base_req=base_req)
        finally:
            ap.OLLAMA_MODEL = _orig
        return result


# ═══════════════════════════════════════════════════════════════════
# Cloud Provider Adapter
# ═══════════════════════════════════════════════════════════════════

class CloudProviderAdapter:
    """Cloud model provider adapter.

    Resolves the cloud provider from configuration and delegates all
    architecture reasoning to the real provider implementation.

    Configuration (env vars):
      AGAINPILOT_CLOUD_PROVIDER=OPENAI    (required for cloud)
      OPENAI_API_KEY=<secret>            (deprecated: AGAINPILOT_CLOUD_API_KEY also works)
      OPENAI_MODEL=gpt-4o                (default: gpt-4o)
    """

    def __init__(self):
        self._provider_name = os.environ.get("AGAINPILOT_CLOUD_PROVIDER", "OPENAI")
        self._impl: Any = None  # Lazy init

    @property
    def role(self) -> ModelRole:
        return ModelRole.CLOUD_EXPERT

    @property
    def model_name(self) -> str:
        impl = self._get_impl()
        if impl:
            return impl.model_name
        return os.environ.get("OPENAI_MODEL", "gpt-4o")

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def is_available(self) -> bool:
        return self._get_impl() is not None

    @property
    def last_usage(self) -> Any:
        impl = self._get_impl()
        if impl and hasattr(impl, "last_usage"):
            return impl.last_usage
        return None

    def _get_impl(self):
        """Lazy-resolve provider implementation."""
        if self._impl is not None:
            return self._impl

        if self._provider_name == "DEEPSEEK":
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                return None
            from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider
            model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
            self._impl = DeepSeekArchitectureProvider(model=model, api_key=api_key)
            return self._impl

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AGAINPILOT_CLOUD_API_KEY")
        if not api_key:
            return None

        if self._provider_name == "OPENAI":
            from infra_again.intelligence.providers.openai_provider import OpenAIArchitectureProvider
            model = os.environ.get("OPENAI_MODEL", "gpt-4o")
            self._impl = OpenAIArchitectureProvider(model=model, api_key=api_key)
        # Future: elif self._provider_name == "ANTHROPIC": ...

        return self._impl

    def generate_intent(self, brief: str, provider_pref: str, platform_pref: str) -> dict | None:
        impl = self._get_impl()
        if not impl:
            return None
        return impl.generate_intent(brief, provider_pref, platform_pref)

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str,
                              req: Any) -> tuple[Any | None, dict]:
        impl = self._get_impl()
        if not impl:
            return None, {"result": "CLOUD_UNAVAILABLE"}
        return impl.generate_architecture(brief, provider_pref, platform_pref, req)

    def refine_architecture(self, nodes: list[dict], edges: list[dict],
                            instruction: str, provider: str,
                            base_req: Any | None = None) -> tuple[Any | None, dict]:
        impl = self._get_impl()
        if not impl:
            return None, {"result": "CLOUD_UNAVAILABLE"}
        return impl.refine_architecture(nodes, edges, instruction, provider, base_req)


# ═══════════════════════════════════════════════════════════════════
# Hybrid Model Router
# ═══════════════════════════════════════════════════════════════════

# Semantic refine instructions that should route directly to CLOUD_EXPERT
# under LOCAL_FIRST policy (local refine is not qualified).
COMPLEX_REFINE_PATTERNS = [
    "change application runtime", "ecs fargate", "topology change",
    "add redis", "add cache", "add queue", "add sqs", "add sns",
    "web application firewall", "waf", "security architecture",
    "data flow", "ha redesign", "high availability redesign",
    "add database", "change database", "remove database",
    "add service", "remove service", "kubernetes", "eks", "gke",
]

def _is_complex_refine(instruction: str) -> bool:
    """Heuristic: does this refine instruction require cloud escalation?"""
    lower = instruction.lower()
    return any(pattern in lower for pattern in COMPLEX_REFINE_PATTERNS)


class HybridModelRouter:
    """Governed model router with local-first escalation.

    Policy:
      LOCAL_ONLY   — never call cloud; return BLOCKED on local failure
      LOCAL_FIRST  — try local, escalate to cloud on failure (default)
      CLOUD_FIRST  — skip local for complex tasks

    Cloud output NEVER bypasses AGAINPILOT governance.  All proposals
    go through the same validators regardless of provider.
    """

    def __init__(
        self,
        local_architect: LocalOllamaProvider | None = None,
        fast_local: LocalOllamaProvider | None = None,
        cloud_expert: CloudProviderAdapter | None = None,
        policy: ExecutionPolicy = ExecutionPolicy.LOCAL_FIRST,
        cloud_allowed: bool = True,
    ):
        self.local_architect = local_architect or LocalOllamaProvider("llama3.1:8b")
        self.fast_local = fast_local or LocalOllamaProvider("qwen2.5:7b", ModelRole.FAST_LOCAL)
        self.cloud_expert = cloud_expert or CloudProviderAdapter()
        self.policy = policy
        self.cloud_allowed = cloud_allowed
        self._last_provenance: RoutingProvenance | None = None

    @property
    def last_provenance(self) -> RoutingProvenance | None:
        return self._last_provenance

    def _capture_token_usage(self, prov: RoutingProvenance):
        """Record token usage from cloud provider if available."""
        try:
            usage = self.cloud_expert.last_usage
            if usage:
                prov.cloud_input_tokens = getattr(usage, "input_tokens", 0)
                prov.cloud_output_tokens = getattr(usage, "output_tokens", 0)
        except Exception:
            pass

    def _effective_cloud_allowed(self, policy: ExecutionPolicy | None = None) -> bool:
        p = policy or self.policy
        if p == ExecutionPolicy.LOCAL_ONLY:
            return False
        return self.cloud_allowed

    # ── Generation ────────────────────────────────────────────────

    def route_generation(
        self, brief: str, provider_pref: str, platform_pref: str, req: Any,
        policy: ExecutionPolicy | None = None,
    ) -> tuple[Any | None, RoutingProvenance]:
        """Route architecture generation according to policy."""
        p = policy or self.policy
        prov = RoutingProvenance(
            request_policy=p.value,
            request_type="generate",
            brief_hash=hashlib.sha256(brief.encode()).hexdigest()[:12],
        )

        # ── CLOUD_FIRST ──
        if p == ExecutionPolicy.CLOUD_FIRST:
            if self._effective_cloud_allowed(p) and self.cloud_expert.is_available():
                return self._try_cloud_generation(brief, provider_pref, platform_pref, req, prov)
            prov.final_result_mode = FinalResultMode.BLOCKED.value
            prov.escalation_reason = EscalationReason.CLOUD_UNAVAILABLE.value
            self._last_provenance = prov
            return None, prov

        # ── LOCAL_ONLY / LOCAL_FIRST: try local first ──
        return self._try_local_generation(brief, provider_pref, platform_pref, req, prov, p)

    def _try_local_generation(
        self, brief: str, provider_pref: str, platform_pref: str, req: Any,
        prov: RoutingProvenance, policy: ExecutionPolicy,
    ) -> tuple[Any | None, RoutingProvenance]:
        prov.local_model = self.local_architect.model_name
        can_escalate = self._effective_cloud_allowed(policy) and self.cloud_expert.is_available()

        t0 = time.time()

        if not self.local_architect.is_available():
            prov.local_result = EscalationReason.LOCAL_MODEL_UNAVAILABLE.value
            prov.local_latency_ms = int((time.time() - t0) * 1000)
            if can_escalate:
                return self._escalate_to_cloud(brief, provider_pref, platform_pref, req, prov, EscalationReason.LOCAL_MODEL_UNAVAILABLE)
            prov.final_result_mode = FinalResultMode.BLOCKED.value
            self._last_provenance = prov
            return None, prov

        # Try local generation
        try:
            proposal, gen_prov = self.local_architect.generate_architecture(brief, provider_pref, platform_pref, req)
        except Exception:
            proposal, gen_prov = None, {"result": EscalationReason.LOCAL_TIMEOUT.value}

        prov.local_latency_ms = int((time.time() - t0) * 1000)
        prov.local_result = gen_prov.get("result", "UNKNOWN")

        # Check quality/completeness
        if proposal:
            from .againpilot import _validate_proposal
            quality, completeness = _validate_proposal(proposal, provider_pref, req)
            if quality.overall.value != "FAIL" and completeness.overall.value != "FAIL":
                prov.final_result_mode = FinalResultMode.LOCAL_ACCEPTED.value
                prov.local_correction_used = gen_prov.get("correctionGenerator") == "REAL_LLM"
                self._last_provenance = prov
                return proposal, prov
            # Local failed quality/completeness
            if gen_prov.get("correctionGenerator") == "REAL_LLM":
                # Already tried correction
                prov.local_correction_used = True
                prov.local_correction_result = "FAILED"
                prov.local_result = EscalationReason.CORRECTION_FAILED.value
            else:
                prov.local_result = EscalationReason.QUALITY_GATE_FAILED.value if quality.overall.value == "FAIL" else EscalationReason.COMPLETENESS_GATE_FAILED.value

        # Local failed — escalate if allowed
        if can_escalate:
            reason = EscalationReason(prov.local_result) if prov.local_result in [e.value for e in EscalationReason] else EscalationReason.QUALITY_GATE_FAILED
            return self._escalate_to_cloud(brief, provider_pref, platform_pref, req, prov, reason)

        prov.final_result_mode = FinalResultMode.BLOCKED.value
        prov.escalated = False
        self._last_provenance = prov
        return None, prov

    def _escalate_to_cloud(
        self, brief: str, provider_pref: str, platform_pref: str, req: Any,
        prov: RoutingProvenance, reason: EscalationReason,
    ) -> tuple[Any | None, RoutingProvenance]:
        prov.escalated = True
        prov.escalation_reason = reason.value
        return self._try_cloud_generation(brief, provider_pref, platform_pref, req, prov)

    def _try_cloud_generation(
        self, brief: str, provider_pref: str, platform_pref: str, req: Any,
        prov: RoutingProvenance,
    ) -> tuple[Any | None, RoutingProvenance]:
        prov.cloud_provider = self.cloud_expert.provider_name
        prov.cloud_model = self.cloud_expert.model_name

        t0 = time.time()
        try:
            proposal, cloud_prov = self.cloud_expert.generate_architecture(brief, provider_pref, platform_pref, req)
        except Exception:
            proposal, cloud_prov = None, {"result": "CLOUD_ERROR"}

        prov.cloud_latency_ms = int((time.time() - t0) * 1000)
        prov.cloud_result = cloud_prov.get("result", "UNKNOWN") if cloud_prov else "CLOUD_UNAVAILABLE"

        # Capture token usage if available
        self._capture_token_usage(prov)

        if not proposal:
            prov.final_result_mode = FinalResultMode.NEEDS_USER_REVIEW.value
            self._last_provenance = prov
            return None, prov

        # Cloud output MUST pass validators — no bypass
        from .againpilot import _validate_proposal
        quality, completeness = _validate_proposal(proposal, provider_pref, req)
        if quality.overall.value == "FAIL" or completeness.overall.value == "FAIL":
            prov.cloud_result = EscalationReason.CLOUD_QUALITY_FAIL.value if quality.overall.value == "FAIL" else EscalationReason.CLOUD_COMPLETENESS_FAIL.value
            prov.final_result_mode = FinalResultMode.BLOCKED.value
            self._last_provenance = prov
            return None, prov

        prov.final_result_mode = FinalResultMode.CLOUD_ESCALATED.value if prov.escalated else FinalResultMode.CLOUD_DIRECT.value
        self._last_provenance = prov
        return proposal, prov

    # ── Refine ────────────────────────────────────────────────────

    def route_refine(
        self, nodes: list[dict], edges: list[dict], instruction: str,
        provider: str, base_req: Any | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> tuple[Any | None, RoutingProvenance]:
        """Route architecture refinement according to policy."""
        p = policy or self.policy
        prov = RoutingProvenance(
            request_policy=p.value,
            request_type="refine",
            brief_hash=hashlib.sha256(instruction.encode()).hexdigest()[:12],
        )

        # Complex semantic refine → cloud directly under LOCAL_FIRST
        if p == ExecutionPolicy.LOCAL_FIRST and _is_complex_refine(instruction):
            if self._effective_cloud_allowed(p) and self.cloud_expert.is_available():
                prov.escalated = True
                prov.escalation_reason = EscalationReason.REFINE_COMPLEX_SEMANTIC.value
                prov.local_model = self.local_architect.model_name
                prov.local_result = "SKIPPED_COMPLEX_REFINE"
                return self._try_cloud_refine(nodes, edges, instruction, provider, prov, base_req)
            # Cloud not available — fall through to local

        # CLOUD_FIRST
        if p == ExecutionPolicy.CLOUD_FIRST:
            if self._effective_cloud_allowed(p) and self.cloud_expert.is_available():
                return self._try_cloud_refine(nodes, edges, instruction, provider, prov, base_req)
            prov.final_result_mode = FinalResultMode.BLOCKED.value
            self._last_provenance = prov
            return None, prov

        # LOCAL_ONLY / LOCAL_FIRST: try local
        return self._try_local_refine(nodes, edges, instruction, provider, prov, p, base_req)

    def _try_local_refine(
        self, nodes: list[dict], edges: list[dict], instruction: str,
        provider: str, prov: RoutingProvenance, policy: ExecutionPolicy,
        base_req: Any | None = None,
    ) -> tuple[Any | None, RoutingProvenance]:
        prov.local_model = self.local_architect.model_name
        can_escalate = self._effective_cloud_allowed(policy) and self.cloud_expert.is_available()

        t0 = time.time()
        if not self.local_architect.is_available():
            prov.local_result = EscalationReason.LOCAL_MODEL_UNAVAILABLE.value
            prov.local_latency_ms = int((time.time() - t0) * 1000)
            if can_escalate:
                return self._escalate_refine_to_cloud(nodes, edges, instruction, provider, prov, EscalationReason.LOCAL_MODEL_UNAVAILABLE, base_req)
            prov.final_result_mode = FinalResultMode.BLOCKED.value
            self._last_provenance = prov
            return None, prov

        try:
            result, refine_prov = self.local_architect.refine_architecture(nodes, edges, instruction, provider, base_req)
        except Exception:
            result, refine_prov = None, {"result": EscalationReason.LOCAL_TIMEOUT.value}

        prov.local_latency_ms = int((time.time() - t0) * 1000)
        prov.local_result = refine_prov.get("result", "UNKNOWN") if refine_prov else "UNKNOWN"

        if result:
            proposal, delta = result
            from .againpilot import _validate_proposal
            quality, completeness = _validate_proposal(proposal, provider, base_req or _dummy_req())
            if quality.overall.value != "FAIL" and completeness.overall.value != "FAIL":
                prov.final_result_mode = FinalResultMode.LOCAL_ACCEPTED.value
                prov.local_correction_used = refine_prov.get("correctionGenerator") == "REAL_LLM"
                self._last_provenance = prov
                return result, prov

        if can_escalate:
            reason = EscalationReason.QUALITY_GATE_FAILED
            return self._escalate_refine_to_cloud(nodes, edges, instruction, provider, prov, reason, base_req)

        prov.final_result_mode = FinalResultMode.BLOCKED.value
        self._last_provenance = prov
        return None, prov

    def _escalate_refine_to_cloud(
        self, nodes: list[dict], edges: list[dict], instruction: str,
        provider: str, prov: RoutingProvenance, reason: EscalationReason,
        base_req: Any | None = None,
    ) -> tuple[Any | None, RoutingProvenance]:
        prov.escalated = True
        prov.escalation_reason = reason.value
        return self._try_cloud_refine(nodes, edges, instruction, provider, prov, base_req)

    def _try_cloud_refine(
        self, nodes: list[dict], edges: list[dict], instruction: str,
        provider: str, prov: RoutingProvenance, base_req: Any | None = None,
    ) -> tuple[Any | None, RoutingProvenance]:
        prov.cloud_provider = self.cloud_expert.provider_name
        prov.cloud_model = self.cloud_expert.model_name

        t0 = time.time()
        try:
            result, cloud_prov = self.cloud_expert.refine_architecture(nodes, edges, instruction, provider, base_req)
        except Exception:
            result, cloud_prov = None, {"result": "CLOUD_ERROR"}

        prov.cloud_latency_ms = int((time.time() - t0) * 1000)
        prov.cloud_result = cloud_prov.get("result", "UNKNOWN") if cloud_prov else "CLOUD_UNAVAILABLE"

        # Capture token usage if available
        self._capture_token_usage(prov)

        if not result:
            prov.final_result_mode = FinalResultMode.NEEDS_USER_REVIEW.value
            self._last_provenance = prov
            return None, prov

        proposal, delta = result
        from .againpilot import _validate_proposal
        quality, completeness = _validate_proposal(proposal, provider, base_req or _dummy_req())
        if quality.overall.value == "FAIL" or completeness.overall.value == "FAIL":
            prov.cloud_result = EscalationReason.CLOUD_QUALITY_FAIL.value if quality.overall.value == "FAIL" else EscalationReason.CLOUD_COMPLETENESS_FAIL.value
            prov.final_result_mode = FinalResultMode.BLOCKED.value
            self._last_provenance = prov
            return None, prov

        prov.final_result_mode = FinalResultMode.CLOUD_ESCALATED.value if prov.escalated else FinalResultMode.CLOUD_DIRECT.value
        self._last_provenance = prov
        return result, prov


def _dummy_req():
    from .againpilot import DetectedRequirement
    return DetectedRequirement(provider="AWS", platform="KUBERNETES", expected_load="MODERATE", availability=[], compliance=[], security=[], data_sensitivity=[])


# ═══════════════════════════════════════════════════════════════════
# Test doubles for router acceptance tests
# ═══════════════════════════════════════════════════════════════════

class TestProviderBase:
    __test__ = False  # Pytest: don't collect this as a test class
    """Base for test doubles."""
    def __init__(self, name: str = "test", role: ModelRole = ModelRole.LOCAL_ARCHITECT, available: bool = True):
        self._name = name
        self._role = role
        self._available = available
        self.call_count = 0

    @property
    def role(self) -> ModelRole: return self._role
    @property
    def model_name(self) -> str: return self._name
    @property
    def provider_name(self) -> str: return "TEST"
    def is_available(self) -> bool: return self._available

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str, req: Any) -> tuple[Any | None, dict]:
        self.call_count += 1
        return None, {"result": "NOT_IMPLEMENTED"}

    def refine_architecture(self, nodes: list[dict], edges: list[dict], instruction: str, provider: str, base_req: Any | None) -> tuple[Any | None, dict]:
        self.call_count += 1
        return None, {"result": "NOT_IMPLEMENTED"}


class PassingTestProvider(TestProviderBase):
    """Test double that always returns a passing proposal."""
    def __init__(self, name: str = "test-passing", role: ModelRole = ModelRole.LOCAL_ARCHITECT):
        super().__init__(name, role)

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str, req: Any) -> tuple[Any | None, dict]:
        self.call_count += 1
        # Return a minimal passing proposal
        from .againpilot import (
            AgainPilotProposal, GeneratedNode, GeneratedEdge,
            DetectedRequirement, _derive_views,
        )
        nodes = [
            GeneratedNode("app", "App", "APPLICATION", provider_pref, "ecs", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("app-b", "App AZ-B", "APPLICATION", provider_pref, "ecs", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("db", "DB", "DATABASE", provider_pref, "rds", "KUBERNETES", "private-data", "pii", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("db-b", "DB AZ-B", "DATABASE", provider_pref, "rds", "KUBERNETES", "private-data", "pii", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("lb", "ALB", "NETWORK", provider_pref, "alb", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("cdn", "CDN", "NETWORK", provider_pref, "cloudfront", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("identity", "Auth", "IDENTITY", provider_pref, "cognito", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("kms", "KMS", "SECURITY", provider_pref, "kms", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("secrets", "Secrets", "SECURITY", provider_pref, "secrets_manager", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("obs", "Obs", "OBSERVABILITY", provider_pref, "cloudwatch", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
        ]
        edges = [
            GeneratedEdge("e1", "user", "cdn", "request", "HTTPS", "unidirectional", "", "none", "User"),
            GeneratedEdge("e2", "cdn", "lb", "request", "HTTPS", "unidirectional", "", "none", "CDN"),
            GeneratedEdge("e3", "lb", "app", "request", "HTTPS", "unidirectional", "", "none", "LB"),
            GeneratedEdge("e3b", "lb", "app-b", "request", "HTTPS", "unidirectional", "", "none", "LB"),
            GeneratedEdge("e4", "app", "db", "data", "TLS", "unidirectional", "", "none", "DB"),
            GeneratedEdge("e4b", "app-b", "db-b", "data", "TLS", "unidirectional", "", "none", "DB"),
            GeneratedEdge("e5", "cdn", "identity", "auth", "HTTPS", "unidirectional", "", "none", "Auth"),
            GeneratedEdge("e6", "app", "identity", "auth", "HTTPS", "unidirectional", "", "none", "Auth"),
            GeneratedEdge("e7", "app", "secrets", "secret", "TLS", "unidirectional", "", "none", "Secrets"),
            GeneratedEdge("e8", "db", "kms", "encrypt", "TLS", "unidirectional", "", "none", "KMS"),
            GeneratedEdge("e9", "app", "obs", "telemetry", "HTTPS", "unidirectional", "", "none", "Obs"),
            GeneratedEdge("e10", "db", "obs", "telemetry", "HTTPS", "unidirectional", "", "none", "Obs"),
        ]
        nd = [n.to_dict() for n in nodes]
        ed = [e.to_dict() for e in edges]
        proposal = AgainPilotProposal(
            title="Test Architecture", summary="Test",
            detected_requirements=req or _dummy_req(),
            nodes=nodes, edges=edges, groups=[],
            views=_derive_views(nd, ed),
            native_service_recommendations=[],
            assumptions=[], risks=[], clarifying_questions=[], rationale="",
            generation_provider="TEST", generation_model=self._name,
            brief_hash="test",
        )
        return proposal, {"result": "REAL_LLM", "qualityResult": "PASS", "completenessResult": "PASS"}

    def refine_architecture(self, nodes: list[dict], edges: list[dict], instruction: str, provider: str, base_req: Any | None) -> tuple[Any | None, dict]:
        """Return a valid refine result."""
        self.call_count += 1
        from .againpilot import (
            AgainPilotProposal, GeneratedNode, GeneratedEdge, RefineDelta, _derive_views,
        )
        req = base_req or _dummy_req()
        p = provider or "AWS"
        # Build fresh nodes/edges inline (don't call generate_architecture to avoid double-counting)
        gnodes = [
            GeneratedNode("app", "App", "APPLICATION", p, "ecs", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("app-b", "App AZ-B", "APPLICATION", p, "ecs", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("db", "DB", "DATABASE", p, "rds", "KUBERNETES", "private-data", "pii", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("db-b", "DB AZ-B", "DATABASE", p, "rds", "KUBERNETES", "private-data", "pii", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("lb", "ALB", "NETWORK", p, "alb", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("cdn", "CDN", "NETWORK", p, "cloudfront", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("identity", "Auth", "IDENTITY", p, "cognito", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("kms", "KMS", "SECURITY", p, "kms", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("secrets", "Secrets", "SECURITY", p, "secrets_manager", "KUBERNETES", "private", "internal", "", "AI_GENERATED", "UNVERIFIED"),
            GeneratedNode("obs", "Obs", "OBSERVABILITY", p, "cloudwatch", "KUBERNETES", "public", "internal", "", "AI_GENERATED", "UNVERIFIED"),
        ]
        gedges = [
            GeneratedEdge("e1", "user", "cdn", "request", "HTTPS", "unidirectional", "", "none", "User"),
            GeneratedEdge("e2", "cdn", "lb", "request", "HTTPS", "unidirectional", "", "none", "CDN"),
            GeneratedEdge("e3", "lb", "app", "request", "HTTPS", "unidirectional", "", "none", "LB"),
            GeneratedEdge("e3b", "lb", "app-b", "request", "HTTPS", "unidirectional", "", "none", "LB"),
            GeneratedEdge("e4", "app", "db", "data", "TLS", "unidirectional", "", "none", "DB"),
            GeneratedEdge("e4b", "app-b", "db-b", "data", "TLS", "unidirectional", "", "none", "DB"),
            GeneratedEdge("e5", "cdn", "identity", "auth", "HTTPS", "unidirectional", "", "none", "Auth"),
            GeneratedEdge("e6", "app", "identity", "auth", "HTTPS", "unidirectional", "", "none", "Auth"),
            GeneratedEdge("e7", "app", "secrets", "secret", "TLS", "unidirectional", "", "none", "Secrets"),
            GeneratedEdge("e8", "db", "kms", "encrypt", "TLS", "unidirectional", "", "none", "KMS"),
            GeneratedEdge("e9", "app", "obs", "telemetry", "HTTPS", "unidirectional", "", "none", "Obs"),
            GeneratedEdge("e10", "db", "obs", "telemetry", "HTTPS", "unidirectional", "", "none", "Obs"),
        ]
        nd = [n.to_dict() for n in gnodes]
        ed = [e.to_dict() for e in gedges]
        proposal = AgainPilotProposal(
            title="Test Refined Architecture", summary=f"Refined: {instruction[:40]}",
            detected_requirements=req, nodes=gnodes, edges=gedges, groups=[],
            views=_derive_views(nd, ed),
            native_service_recommendations=[],
            assumptions=[], risks=[], clarifying_questions=[], rationale="",
            generation_provider="TEST", generation_model=self._name,
            brief_hash="test-refine",
        )
        delta = RefineDelta(
            added_nodes=[], removed_nodes=[],
            changed_nodes=[
                {"nodeId": "app", "field": "notes",
                 "oldValue": "", "newValue": f"Refined: {instruction[:40]}"},
            ],
            added_edges=[], removed_edges=[],
        )
        return (proposal, delta), {"result": "REAL_LLM_REFINE", "qualityResult": "PASS", "completenessResult": "PASS"}


class FailingTestProvider(TestProviderBase):
    """Test double that always fails."""
    def __init__(self, name: str = "test-failing", role: ModelRole = ModelRole.LOCAL_ARCHITECT):
        super().__init__(name, role)

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str, req: Any) -> tuple[Any | None, dict]:
        self.call_count += 1
        return None, {"result": "QUALITY_FAIL", "qualityResult": "FAIL", "completenessResult": "PASS"}

    def refine_architecture(self, nodes: list[dict], edges: list[dict], instruction: str, provider: str, base_req: Any | None) -> tuple[Any | None, dict]:
        self.call_count += 1
        return None, {"result": "QUALITY_FAIL"}
