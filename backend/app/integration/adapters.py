"""
Integration Adapters — connect to sibling Again Platform apps.
"""

import os
import hashlib
import hmac
import time
from typing import Any

import httpx

# ── Service Registry ──────────────────────────────────────

SERVICES = {
    "pm-again": {
        "name": "PM Again",
        "base_url": os.getenv("PM_AGAIN_URL", "https://pmagain.kanphong.com"),
        "api_prefix": "/api",
        "service_token": os.getenv("PM_AGAIN_SERVICE_TOKEN", ""),
        "status": "CONNECTED",
        "description": "Project management and delivery planning",
    },
    "qa-again": {
        "name": "QA Again",
        "base_url": os.getenv("QA_AGAIN_URL", "https://qaagain.kanphong.com"),
        "api_prefix": "/api",
        "service_token": os.getenv("QA_AGAIN_SERVICE_TOKEN", ""),
        "status": "DEPLOYING",
        "description": "Quality engineering, test evidence, defect tracking",
    },
    "dev-again": {
        "name": "Dev Again",
        "base_url": os.getenv("DEV_AGAIN_URL", ""),
        "api_prefix": "/api",
        "service_token": os.getenv("DEV_AGAIN_SERVICE_TOKEN", ""),
        "status": "PLANNED",
        "description": "Developer integration layer",
    },
}


def get_service(name: str) -> dict | None:
    return SERVICES.get(name)


async def call_service(
    service_name: str,
    method: str,
    path: str,
    json_data: dict | None = None,
    params: dict | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Make an authenticated call to a sibling Again Platform service."""
    svc = SERVICES.get(service_name)
    if not svc:
        raise ValueError(f"Unknown service: {service_name}")
    if svc["status"] == "PENDING_DEPLOYMENT":
        return {"ok": False, "error": f"{svc['name']} is not yet deployed", "status": "PENDING_DEPLOYMENT"}
    if svc["status"] == "DEPLOYING":
        return {"ok": False, "error": f"{svc['name']} is deploying — estimated 24h", "status": "DEPLOYING"}
    if svc["status"] == "PLANNED":
        return {"ok": False, "error": f"{svc['name']} is planned but not built", "status": "PLANNED"}

    url = f"{svc['base_url'].rstrip('/')}{svc['api_prefix']}{path}"
    headers = {"Content-Type": "application/json"}

    if svc.get("service_token"):
        headers["Authorization"] = f"Bearer {svc['service_token']}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(method, url, json=json_data, params=params, headers=headers)
            try:
                return {"ok": resp.is_success, "status_code": resp.status_code, "data": resp.json()}
            except Exception:
                return {"ok": False, "status_code": resp.status_code, "error": resp.text[:500]}
        except httpx.ConnectError:
            return {"ok": False, "error": f"Cannot connect to {svc['name']} at {url}", "status": "UNREACHABLE"}
        except httpx.TimeoutException:
            return {"ok": False, "error": f"{svc['name']} timed out", "status": "TIMEOUT"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:500], "status": "ERROR"}


# ── PM Again Integration ──────────────────────────────────

async def pm_create_delivery_plan(
    project_slug: str,
    requirements: list[dict],
    vision_title: str = "",
) -> dict:
    """Send approved requirements to PM Again for delivery planning.
    
    PM Again owns: Project, Epic, Feature, Task, Timeline, Milestone, Sprint.
    Conductor sends: requirement references, vision context, traceability data.
    """
    return await call_service(
        "pm-again",
        "POST",
        f"/projects/{project_slug}/delivery-plan",
        json_data={
            "source": "conductor-again",
            "source_project": project_slug,
            "vision_title": vision_title,
            "requirements": [
                {
                    "code": r.get("code", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                    "priority": r.get("priority", 0),
                    "conductor_ref_id": r.get("id", ""),
                }
                for r in requirements
            ],
            "traceability": {
                "vision_revision": 1,
                "baseline_approved": True,
            },
        },
    )


async def pm_get_artifact_references(project_slug: str) -> dict:
    """Fetch PM Again artifact references for a project."""
    return await call_service(
        "pm-again",
        "GET",
        f"/projects/{project_slug}/artifacts",
    )


async def pm_get_plan_status(project_slug: str) -> dict:
    """Check PM Again delivery plan status."""
    return await call_service(
        "pm-again",
        "GET",
        f"/projects/{project_slug}/status",
    )


# ── QA Again Integration ──────────────────────────────────

async def qa_create_quality_design(
    project_slug: str,
    requirements: list[dict],
) -> dict:
    """Send requirements to QA Again for test design.
    
    QA Again owns: Test Suite, Test Case, Execution Result, Evidence, Defect.
    Conductor sends: requirement references for test coverage.
    """
    return await call_service(
        "qa-again",
        "POST",
        f"/projects/{project_slug}/quality-design",
        json_data={
            "source": "conductor-again",
            "source_project": project_slug,
            "requirements": [
                {
                    "code": r.get("code", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                    "conductor_ref_id": r.get("id", ""),
                }
                for r in requirements
            ],
        },
    )


async def qa_get_coverage_summary(project_slug: str) -> dict:
    """Fetch QA Again test coverage summary."""
    return await call_service(
        "qa-again",
        "GET",
        f"/projects/{project_slug}/coverage",
    )


async def qa_request_retest(project_slug: str, defect_id: str) -> dict:
    """Request retest after a defect fix."""
    return await call_service(
        "qa-again",
        "POST",
        f"/projects/{project_slug}/retest",
        json_data={
            "source": "conductor-again",
            "defect_id": defect_id,
        },
    )


# ── Health Check ──────────────────────────────────────────

async def check_service_health(service_name: str) -> dict:
    """Check if a sibling service is reachable."""
    svc = SERVICES.get(service_name)
    if not svc:
        return {"ok": False, "error": f"Unknown: {service_name}"}
    
    if svc["status"] in ("PENDING_DEPLOYMENT", "PLANNED"):
        return {"ok": False, "status": svc["status"], "message": svc["description"]}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{svc['base_url'].rstrip('/')}/api/health")
            return {
                "ok": resp.is_success,
                "status_code": resp.status_code,
                "service": svc["name"],
                "url": svc["base_url"],
            }
    except Exception as e:
        return {"ok": False, "error": str(e), "service": svc["name"]}
