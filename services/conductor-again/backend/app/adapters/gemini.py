"""
Google Gemini Adapter — Official API
Base URL: https://generativelanguage.googleapis.com/v1beta
"""

import time
from typing import Any

import httpx

from app.adapters.base import AIRequest, AIResponse, AdapterHealth, BaseAdapter


_ROLE_MAP = {
    "system": "user",
    "user": "user",
    "assistant": "model",
}


class GeminiAdapter(BaseAdapter):
    """Google Gemini API adapter.

    Models include: gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash, etc.
    """

    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _convert_messages(self, messages: list[dict]) -> tuple[list[dict], str | None]:
        """Convert OpenAI-format messages to Gemini format.
        Returns (contents, system_instruction).
        """
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            gemini_role = _ROLE_MAP.get(role, "user")
            if role == "system":
                system_instruction = msg.get("content", "")
            else:
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": msg.get("content", "")}],
                })
        return contents, system_instruction

    async def health(self) -> AdapterHealth:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models?key={self.api_key}",
                )
                if resp.status_code == 200:
                    return AdapterHealth(ok=True, message="Gemini API reachable")
                elif resp.status_code in (401, 403):
                    return AdapterHealth(ok=False, message="Invalid Gemini API key")
                elif resp.status_code == 429:
                    return AdapterHealth(ok=False, message="Gemini rate limited")
                else:
                    return AdapterHealth(ok=False, message=f"Gemini returned {resp.status_code}")
        except Exception as e:
            return AdapterHealth(ok=False, message=f"Connection failed: {str(e)}")

    async def chat(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()

        contents, system_instruction = self._convert_messages(request.messages)

        generation_config: dict[str, Any] = {
            "maxOutputTokens": request.max_tokens,
            "temperature": request.temperature,
        }

        if request.structured_output_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = request.structured_output_schema

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        url = f"{self.base_url}/models/{request.model_id}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        usage = data.get("usageMetadata", {})

        content = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts)

        finish_reason = "stop"
        if candidates:
            fr = candidates[0].get("finishReason", "STOP")
            finish_reason = fr.lower()

        return AIResponse(
            content=content,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            model_used=data.get("modelVersion", request.model_id),
            latency_ms=int((time.monotonic() - start) * 1000),
            finish_reason=finish_reason,
            raw_response=data,
        )

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models?key={self.api_key}",
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    m["name"].replace("models/", "")
                    for m in data.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
        except Exception:
            return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]


def create_gemini_adapter(api_key: str) -> GeminiAdapter:
    return GeminiAdapter(api_key=api_key)
