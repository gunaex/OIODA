"""Provider Intelligence Resolution API — Phase N1.5.

Read-only. No secrets, no raw cloud credentials — this only ever returns
catalog metadata and deterministic resolution verdicts.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .catalog import get_catalog
from .provider_resolver import get_resolver


class ArchitectureSummaryRequest(BaseModel):
    nodes: list[dict[str, Any]] = []


def register_provider_resolver_routes(app: FastAPI) -> None:
    resolver = get_resolver()
    catalog = get_catalog()

    # ── Single service resolution ──

    @app.get("/api/v1/provider-intelligence/resolve")
    async def resolve_service(provider: str, nativeService: str, platform: str = ""):
        """Resolve one (provider, nativeService, platform) tuple against the
        authoritative catalog. Never called by the LLM — only by product code
        after a proposal already exists."""
        try:
            result = resolver.resolve(provider=provider, native_service=nativeService, platform=platform)
            return {"resolution": result.to_dict()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Resolution failed: {e}")

    # ── Architecture-level resolution summary ──

    @app.post("/api/v1/provider-intelligence/architecture-summary")
    async def architecture_summary(body: ArchitectureSummaryRequest):
        """Resolve every node in a proposed/loaded architecture. Per-node
        resolutions plus simple aggregate counts — NOT a feasibility verdict
        (that's a separate, richer model — see Phase N2)."""
        try:
            resolutions = []
            for n in body.nodes:
                if n.get("category") in ("USER", "EXTERNAL") or not n.get("nativeService"):
                    continue
                r = resolver.resolve(
                    provider=n.get("provider", ""), native_service=n.get("nativeService", ""),
                    platform=n.get("platform", ""),
                )
                resolutions.append({"nodeId": n.get("nodeId", ""), **r.to_dict()})

            counts: dict[str, int] = {}
            for r in resolutions:
                state = r["providerLifecycleState"]
                counts[state] = counts.get(state, 0) + 1

            return {
                "totalServices": len(resolutions),
                "lifecycleCounts": counts,
                "unknownServiceCount": counts.get("UNKNOWN_SERVICE", 0),
                "executableCount": sum(1 for r in resolutions if r["executorAvailable"]),
                "resolutions": resolutions,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Architecture summary failed: {e}")

    # ── Supported services by provider/platform ──

    @app.get("/api/v1/provider-intelligence/services")
    async def supported_services(provider: str, platform: str = ""):
        """List every catalogued service for a provider, each with its
        resolved state — lets the UI show what's actually known/executable
        without the caller having to enumerate service names first."""
        try:
            services = catalog.get_services(provider.upper())
            out = []
            for svc in services:
                r = resolver.resolve(provider=provider, native_service=svc.service_id, platform=platform)
                out.append(r.to_dict())
            return {"provider": provider.upper(), "platform": platform or None, "services": out}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Service listing failed: {e}")
