"""
Adapter Registry — maps provider codes to adapter constructors.
All adapters follow the BaseAdapter contract.
"""

from app.adapters.base import BaseAdapter
from app.adapters.deepseek import create_deepseek_adapter
from app.adapters.openai import create_openai_adapter
from app.adapters.gemini import create_gemini_adapter
from app.adapters.anthropic import create_anthropic_adapter
from app.adapters.cloudflare_workers import create_workers_ai_adapter

# Maps provider_code → adapter factory
ADAPTER_REGISTRY: dict[str, callable] = {
    "deepseek": lambda key, **kw: create_deepseek_adapter(key),
    "openai": lambda key, **kw: create_openai_adapter(key),
    "gemini": lambda key, **kw: create_gemini_adapter(key),
    "anthropic": lambda key, **kw: create_anthropic_adapter(key),
    "cloudflare": lambda key, **kw: create_workers_ai_adapter(
        api_token=key,
        account_id=kw.get("account_id", ""),
    ),
}

PLANNED_PROVIDERS = {
    "ollama": "PLANNED",
    "vllm": "PLANNED",
    "lm-studio": "PLANNED",
    "codex": "PLANNED",
    "claude-code": "PLANNED",
    "gemini-cli": "PLANNED",
}


def get_adapter(provider_code: str, api_key: str, **kwargs) -> BaseAdapter | None:
    """Create an adapter instance for the given provider, or None if unsupported."""
    factory = ADAPTER_REGISTRY.get(provider_code)
    if factory:
        return factory(api_key, **kwargs)
    return None


__all__ = [
    "ADAPTER_REGISTRY",
    "PLANNED_PROVIDERS",
    "get_adapter",
]
