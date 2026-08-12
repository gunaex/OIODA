"""
Cloudflare Workers AI Adapter
Base URL: https://api.cloudflare.com/client/v4/accounts/{account_id}/ai
"""

import time
from typing import Any

import httpx

from app.adapters.base import AIRequest, AIResponse, AdapterHealth, BaseAdapter


class CloudflareWorkersAIAdapter(BaseAdapter):
    """Cloudflare Workers AI adapter.

    Uses the Workers AI REST API.
    Models include: @cf/meta/llama-3*, @cf/deepseek-ai/deepseek-r1*, etc.
    """

    def __init__(self, api_token: str, account_id: str, base_url: str = ""):
        self.api_token = api_token
        self.account_id = account_id
        self.base_url = base_url.rstrip("/") or (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai"
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def health(self) -> AdapterHealth:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Use a lightweight model for health check
                resp = await client.post(
                    f"{self.base_url}/run/@cf/meta/llama-3-8b-instruct",
                    headers=self._headers(),
                    json={
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                if resp.status_code == 200:
                    return AdapterHealth(ok=True, message="Workers AI reachable")
                elif resp.status_code == 401:
                    return AdapterHealth(ok=False, message="Invalid Cloudflare API token")
                elif resp.status_code == 429:
                    return AdapterHealth(ok=False, message="Workers AI rate limited")
                else:
                    return AdapterHealth(ok=False, message=f"Workers AI returned {resp.status_code}")
        except Exception as e:
            return AdapterHealth(ok=False, message=f"Connection failed: {str(e)}")

    async def chat(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()

        payload: dict[str, Any] = {
            "messages": request.messages,
            "max_tokens": request.max_tokens,
        }

        if request.temperature:
            payload["temperature"] = request.temperature

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/run/{request.model_id}",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", {})
        content = ""
        if isinstance(result, dict):
            content = result.get("response", "")
        elif isinstance(result, str):
            content = result

        return AIResponse(
            content=content,
            input_tokens=0,  # Workers AI doesn't consistently report tokens
            output_tokens=0,
            model_used=request.model_id,
            latency_ms=int((time.monotonic() - start) * 1000),
            finish_reason="stop",
            raw_response=data,
        )

    async def list_models(self) -> list[str]:
        """List available Workers AI models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                models = []
                for m in data.get("result", []):
                    if m.get("task", {}).get("name") == "Text Generation":
                        models.append(m.get("name", ""))
                return models
        except Exception:
            return [
                "@cf/meta/llama-3-8b-instruct",
                "@cf/meta/llama-3-70b-instruct",
                "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
                "@cf/mistral/mistral-7b-instruct-v0.2",
            ]


def create_workers_ai_adapter(api_token: str, account_id: str) -> CloudflareWorkersAIAdapter:
    return CloudflareWorkersAIAdapter(api_token=api_token, account_id=account_id)
