"""
AI Provider Adapter Interface
All adapters must implement this base contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIRequest:
    """Normalized AI request across all providers."""
    messages: list[dict[str, Any]]
    model_id: str
    max_tokens: int = 2048
    temperature: float = 0.7
    structured_output_schema: dict | None = None
    tools: list[dict] | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class AIResponse:
    """Normalized AI response."""
    content: str | None = None
    structured_output: dict | None = None
    tool_calls: list[dict] | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    model_used: str = ""
    latency_ms: int = 0
    finish_reason: str = "stop"
    raw_response: dict | None = None


@dataclass
class AdapterHealth:
    """Health check result from an adapter."""
    ok: bool
    message: str = ""
    remaining_quota: float | None = None
    reset_at: str | None = None


class BaseAdapter(ABC):
    """Every AI provider adapter must extend this."""

    @abstractmethod
    async def health(self) -> AdapterHealth:
        """Check connectivity and quota."""
        ...

    @abstractmethod
    async def chat(self, request: AIRequest) -> AIResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List available model IDs from the provider."""
        ...
