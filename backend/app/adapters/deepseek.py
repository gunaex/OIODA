"""
DeepSeek Adapter — OpenAI-compatible API
Base URL: https://api.deepseek.com
"""

import os
import time
from typing import Any

import httpx

from app.adapters.base import AIRequest, AIResponse, AdapterHealth, BaseAdapter


class DeepSeekAdapter(BaseAdapter):
    """DeepSeek API adapter (OpenAI-compatible).

    Models:
      - deepseek-chat      (general purpose, 64K context)
      - deepseek-reasoner  (reasoning-focused)
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def health(self) -> AdapterHealth:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return AdapterHealth(ok=True, message="DeepSeek API reachable")
                elif resp.status_code == 401:
                    return AdapterHealth(ok=False, message="Invalid DeepSeek API key")
                elif resp.status_code == 429:
                    return AdapterHealth(ok=False, message="DeepSeek rate limited")
                else:
                    return AdapterHealth(ok=False, message=f"DeepSeek returned {resp.status_code}")
        except Exception as e:
            return AdapterHealth(ok=False, message=f"Connection failed: {str(e)}")

    async def chat(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()

        payload: dict[str, Any] = {
            "model": request.model_id,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        # Structured output (JSON mode)
        if request.structured_output_schema:
            payload["response_format"] = {
                "type": "json_object",
            }
            # Inject schema instruction into system message
            schema_instruction = {
                "role": "system",
                "content": f"You must respond with valid JSON matching this schema:\n{request.structured_output_schema}",
            }
            payload["messages"] = [schema_instruction] + request.messages

        # Tool calling
        if request.tools:
            payload["tools"] = request.tools

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})
        msg = choice.get("message", {})

        return AIResponse(
            content=msg.get("content"),
            structured_output=None,  # Parse from content if JSON mode
            tool_calls=msg.get("tool_calls"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model_used=data.get("model", request.model_id),
            latency_ms=int((time.monotonic() - start) * 1000),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            # Return known models if API call fails
            return ["deepseek-chat", "deepseek-reasoner"]


# ── Adapter Factory ───────────────────────────────────────

def create_deepseek_adapter(api_key: str) -> DeepSeekAdapter:
    return DeepSeekAdapter(api_key=api_key)
