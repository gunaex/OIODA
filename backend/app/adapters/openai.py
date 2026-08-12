"""
OpenAI Adapter — Official API
Base URL: https://api.openai.com/v1
"""

import time
from typing import Any

import httpx

from app.adapters.base import AIRequest, AIResponse, AdapterHealth, BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """OpenAI API adapter.

    Models include: gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o3-mini, etc.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
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
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return AdapterHealth(ok=True, message="OpenAI API reachable")
                elif resp.status_code == 401:
                    return AdapterHealth(ok=False, message="Invalid OpenAI API key")
                elif resp.status_code == 429:
                    return AdapterHealth(ok=False, message="OpenAI rate limited")
                else:
                    return AdapterHealth(ok=False, message=f"OpenAI returned {resp.status_code}")
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

        if request.structured_output_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": request.structured_output_schema,
                    "strict": True,
                },
            }

        if request.tools:
            payload["tools"] = request.tools

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
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
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return [m["id"] for m in data.get("data", []) if m["id"].startswith(("gpt-", "o1", "o3"))]
        except Exception:
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"]


def create_openai_adapter(api_key: str) -> OpenAIAdapter:
    return OpenAIAdapter(api_key=api_key)
