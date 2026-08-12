"""
Anthropic Claude Adapter — Official API
Base URL: https://api.anthropic.com/v1
"""

import time
from typing import Any

import httpx

from app.adapters.base import AIRequest, AIResponse, AdapterHealth, BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Anthropic Claude API adapter.

    Models include: claude-sonnet-4-20250514, claude-opus-4-20250514,
    claude-3-5-haiku-20241022, etc.
    """

    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Convert OpenAI-format messages to Anthropic format.
        Returns (system_message, messages).
        """
        system = None
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system = content
            elif role == "assistant":
                converted.append({"role": "assistant", "content": content})
            else:
                converted.append({"role": "user", "content": content})
        return system, converted

    async def health(self) -> AdapterHealth:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return AdapterHealth(ok=True, message="Anthropic API reachable")
                elif resp.status_code == 401:
                    return AdapterHealth(ok=False, message="Invalid Anthropic API key")
                elif resp.status_code == 429:
                    return AdapterHealth(ok=False, message="Anthropic rate limited")
                else:
                    return AdapterHealth(ok=False, message=f"Anthropic returned {resp.status_code}")
        except Exception as e:
            return AdapterHealth(ok=False, message=f"Connection failed: {str(e)}")

    async def chat(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()

        system_msg, messages = self._convert_messages(request.messages)

        payload: dict[str, Any] = {
            "model": request.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }

        if system_msg:
            payload["system"] = system_msg

        if request.temperature != 0.7:
            payload["temperature"] = request.temperature

        if request.tools:
            payload["tools"] = request.tools

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/messages",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content_blocks = data.get("content", [])
        text_content = ""
        tool_calls = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": str(block.get("input", {})),
                    },
                })

        usage = data.get("usage", {})

        return AIResponse(
            content=text_content if text_content else None,
            tool_calls=tool_calls if tool_calls else None,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model_used=data.get("model", request.model_id),
            latency_ms=int((time.monotonic() - start) * 1000),
            finish_reason=data.get("stop_reason", "end_turn"),
            raw_response=data,
        )

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            return [
                "claude-sonnet-4-20250514",
                "claude-opus-4-20250514",
                "claude-3-5-haiku-20241022",
            ]


def create_anthropic_adapter(api_key: str) -> AnthropicAdapter:
    return AnthropicAdapter(api_key=api_key)
