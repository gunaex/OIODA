"""
Conductor Again — AI Resources Router
Full CRUD for Providers, Accounts, Runtimes, Models, and Resources.
"""

import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.auth import get_current_user, require_roles
from app.database import get_master_db
from app.integration.lacc_client import LocalAIControlCenterClient
from app.models import (
    AIAccount,
    AIExecutionRuntime,
    AIProvider,
    AIResource,
    HealthSnapshot,
    InstalledModel,
    RoutingDecision,
    User,
)
from app.schemas import (
    AIAccountCreate,
    AIAccountOut,
    AIAccountUpdate,
    AIProviderCreate,
    AIProviderOut,
    AIResourceCreate,
    AIResourceOut,
    AIResourcePoolSummary,
    AIRuntimeCreate,
    AIRuntimeOut,
    InstalledModelCreate,
    InstalledModelOut,
)

router = APIRouter(prefix="/api/ai", tags=["ai-resources"])

ECOSYSTEM_MODE = os.getenv("ECOSYSTEM_MODE", "false").lower() == "true"

# ── Encryption ────────────────────────────────────────────
_ENCRYPTION_KEY = os.getenv("AI_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode())
_cipher = Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)


def _encrypt(plain: str) -> str:
    if not plain:
        return ""
    return _cipher.encrypt(plain.encode()).decode()


def _decrypt(encrypted: str) -> str:
    if not encrypted:
        return ""
    try:
        return _cipher.decrypt(encrypted.encode()).decode()
    except Exception:
        return "[encrypted]"


# ═══════════════════════════════════════════════════════════
# AI Providers
# ═══════════════════════════════════════════════════════════

@router.get("/providers", response_model=list[AIProviderOut])
def list_providers(
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    return db.query(AIProvider).order_by(AIProvider.name).all()


@router.post("/providers", response_model=AIProviderOut, status_code=201)
def create_provider(
    body: AIProviderCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    existing = db.query(AIProvider).filter(AIProvider.code == body.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Provider code already exists")
    provider = AIProvider(**body.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


@router.patch("/providers/{provider_id}", response_model=AIProviderOut)
def update_provider(
    provider_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    for key in ["name", "website", "description", "logo_url"]:
        if key in body and body[key] is not None:
            setattr(provider, key, body[key])
    if "enabled" in body:
        provider.enabled = body["enabled"]
    db.commit()
    db.refresh(provider)
    return provider


# ═══════════════════════════════════════════════════════════
# AI Accounts
# ═══════════════════════════════════════════════════════════

@router.get("/accounts", response_model=list[AIAccountOut])
def list_accounts(
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    return db.query(AIAccount).order_by(AIAccount.name).all()


@router.post("/accounts", response_model=AIAccountOut, status_code=201)
def create_account(
    body: AIAccountCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    provider = db.query(AIProvider).filter(AIProvider.id == body.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    api_key = body.api_key
    data = body.model_dump(exclude={"api_key"})
    data["api_key_encrypted"] = _encrypt(api_key)
    data["api_key_last4"] = api_key[-4:] if api_key else ""

    account = AIAccount(**data)
    db.add(account)
    db.flush()  # Generate the UUID before creating runtime

    # Auto-create a default runtime for API accounts
    if body.account_type == "api" and body.access_mode == "OFFICIAL_API":
        runtime = AIExecutionRuntime(
            account_id=account.id,
            runtime_type="OFFICIAL_API",
            endpoint_url=body.api_base_url,
        )
        db.add(runtime)
        db.flush()

        # Auto-register default models based on provider
        _register_default_models(db, provider.code, runtime, body.api_base_url)

    db.commit()
    db.refresh(account)
    return account


@router.patch("/accounts/{account_id}", response_model=AIAccountOut)
def update_account(
    account_id: str,
    body: AIAccountUpdate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    account = db.query(AIAccount).filter(AIAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    update_data = body.model_dump(exclude_unset=True)
    if "api_key" in update_data:
        key = update_data.pop("api_key")
        if key:
            update_data["api_key_encrypted"] = _encrypt(key)
            update_data["api_key_last4"] = key[-4:]

    for key, val in update_data.items():
        setattr(account, key, val)

    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: str,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    """Delete an AI account and all its runtimes, models, and resources (cascade)."""
    account = db.query(AIAccount).filter(AIAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"ok": True, "deleted": account.name}


# ═══════════════════════════════════════════════════════════
# AI Execution Runtimes
# ═══════════════════════════════════════════════════════════

@router.get("/runtimes", response_model=list[AIRuntimeOut])
def list_runtimes(
    account_id: str | None = Query(None),
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    q = db.query(AIExecutionRuntime)
    if account_id:
        q = q.filter(AIExecutionRuntime.account_id == account_id)
    return q.order_by(AIExecutionRuntime.runtime_type).all()


@router.post("/runtimes", response_model=AIRuntimeOut, status_code=201)
def create_runtime(
    body: AIRuntimeCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    runtime = AIExecutionRuntime(**body.model_dump())
    db.add(runtime)
    db.commit()
    db.refresh(runtime)
    return runtime


# ═══════════════════════════════════════════════════════════
# Installed Models
# ═══════════════════════════════════════════════════════════

@router.get("/models", response_model=list[InstalledModelOut])
def list_models(
    runtime_id: str | None = Query(None),
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    q = db.query(InstalledModel)
    if runtime_id:
        q = q.filter(InstalledModel.runtime_id == runtime_id)
    return q.order_by(InstalledModel.display_name).all()


@router.post("/models", response_model=InstalledModelOut, status_code=201)
def create_model(
    body: InstalledModelCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    model = InstalledModel(**body.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


# ═══════════════════════════════════════════════════════════
# AI Resources (routable combinations)
# ═══════════════════════════════════════════════════════════

@router.get("/resources", response_model=list[AIResourceOut])
def list_resources(
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    return db.query(AIResource).order_by(AIResource.display_name).all()


@router.post("/resources", response_model=AIResourceOut, status_code=201)
def create_resource(
    body: AIResourceCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    resource = AIResource(**body.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.patch("/resources/{resource_id}", response_model=AIResourceOut)
def update_resource(
    resource_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    resource = db.query(AIResource).filter(AIResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    for key in ["display_name", "entitlements", "allowed_data_classifications",
                 "allowed_projects", "base_priority", "max_concurrency", "health_state"]:
        if key in body and body[key] is not None:
            setattr(resource, key, body[key])
    if "enabled" in body:
        resource.enabled = body["enabled"]
    db.commit()
    db.refresh(resource)
    return resource


# ═══════════════════════════════════════════════════════════
# Pool Summary & Health
# ═══════════════════════════════════════════════════════════

@router.get("/pool-summary", response_model=AIResourcePoolSummary)
def pool_summary(
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    resources = db.query(AIResource).all()
    return AIResourcePoolSummary(
        total_resources=len(resources),
        available=sum(1 for r in resources if r.health_state == "AVAILABLE" and r.enabled),
        busy=sum(1 for r in resources if r.health_state == "BUSY"),
        degraded=sum(1 for r in resources if r.health_state == "DEGRADED"),
        offline=sum(1 for r in resources if r.health_state in ("OFFLINE", "AUTH_EXPIRED", "SUSPENDED", "REVOKED")),
        rate_limited=sum(1 for r in resources if r.health_state == "RATE_LIMITED"),
        provider_count=db.query(AIProvider).count(),
        account_count=db.query(AIAccount).count(),
        model_count=db.query(InstalledModel).count(),
    )


@router.post("/accounts/{account_id}/health-check")
async def health_check_account(
    account_id: str,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    account = db.query(AIAccount).filter(AIAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if ECOSYSTEM_MODE:
        # CONDUCTOR_RAW_AI_CREDENTIAL_AUTHORITY_REMOVED (E8.1-G): in ecosystem mode,
        # Conductor never decrypts AIAccount.api_key_encrypted at runtime — provider
        # health/connectivity is Local AI Control Center's concern (Ollama health) or
        # Account Again's (credential status), not Conductor's own credential probe.
        return {
            "ok": None,
            "message": "LEGACY_CREDENTIAL_HEALTH_CHECK_DISABLED_IN_ECOSYSTEM_MODE: "
                        "Conductor does not read AIAccount.api_key_encrypted at runtime "
                        "in ecosystem mode. Use Local AI Control Center's own health "
                        "endpoint for provider/model availability.",
        }

    if not account.api_key_encrypted:
        return {"ok": False, "message": "No API key configured"}

    api_key = _decrypt(account.api_key_encrypted)
    provider_code = account.provider.code if account.provider else "unknown"

    try:
        adapter = get_adapter(provider_code, api_key, account_id=account.id)
        if adapter:
            health = await adapter.health()
            account.health_state = "AVAILABLE" if health.ok else "AUTH_EXPIRED"
            account.last_health_check = datetime.now(timezone.utc)

            # Record health snapshot
            snapshot = HealthSnapshot(
                resource_id=None,  # account-level check
                account_id=account.id,
                state=account.health_state,
                message=health.message,
            )
            db.add(snapshot)
            db.commit()
            return {"ok": health.ok, "message": health.message}
        else:
            # Generic check: try a simple HTTP call
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{account.api_base_url}/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                ok = resp.status_code == 200
                account.health_state = "AVAILABLE" if ok else "AUTH_EXPIRED"
                account.last_health_check = datetime.now(timezone.utc)
                db.commit()
                return {"ok": ok, "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        account.health_state = "OFFLINE"
        account.last_health_check = datetime.now(timezone.utc)
        return {"ok": False, "message": str(e)}


@router.post("/resources/{resource_id}/test")
async def test_resource(
    resource_id: str,
    prompt: str = "Say hello in one short sentence.",
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    """Quick test: send a prompt through the selected resource."""
    resource = db.query(AIResource).filter(AIResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    if ECOSYSTEM_MODE:
        # AIExecutionGateway path — no AIResource/api_key_encrypted lookup at all.
        result = LocalAIControlCenterClient.execute_capability(
            capability="GENERAL_REASONING", correlation_id=f"corr-restest-{resource_id}",
            prompt=prompt, request_id=f"req-restest-{resource_id[:8]}",
        )
        if result.get("status") != "COMPLETED":
            return {"ok": False, "error": result.get("outputSummary", "AI execution failed")}
        return {
            "ok": True, "response": result.get("outputSummary"),
            "model": result.get("modelUsed"), "provider": result.get("providerUsed"),
            "evidence_ref": result.get("evidenceRef"),
        }

    account = resource.account
    if not account or not account.api_key_encrypted:
        raise HTTPException(status_code=400, detail="No API key configured for this account")

    api_key = _decrypt(account.api_key_encrypted)
    provider_code = account.provider.code if account.provider else "unknown"
    model_id = resource.model.model_id if resource.model else "deepseek-chat"

    try:
        from app.adapters.base import AIRequest

        adapter = get_adapter(provider_code, api_key)
        if adapter:
            response = await adapter.chat(AIRequest(
                messages=[{"role": "user", "content": prompt}],
                model_id=model_id,
                max_tokens=100,
            ))
            return {
                "ok": True,
                "response": response.content,
                "model": response.model_used,
                "tokens": {"input": response.input_tokens, "output": response.output_tokens},
                "latency_ms": response.latency_ms,
            }
        else:
            # Fallback: generic OpenAI-compatible call
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{account.api_base_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 100,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "ok": True,
                    "response": data["choices"][0]["message"]["content"],
                    "model": data.get("model", model_id),
                    "tokens": data.get("usage", {}),
                }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# Default Model Registration
# ═══════════════════════════════════════════════════════════

_DEFAULT_MODELS = {
    "deepseek": [
        {
            "model_id": "deepseek-chat",
            "display_name": "DeepSeek Chat (V3)",
            "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                             "LONG_CONTEXT", "CODE_REASONING", "MULTILINGUAL", "THAI_LANGUAGE"],
            "context_limit": 65536,
            "input_types": ["text"],
            "output_types": ["text", "json"],
            "pricing_per_1k_input": 0.00027,
            "pricing_per_1k_output": 0.00110,
            "latency_class": "balanced",
            "quality_class": "premium",
        },
        {
            "model_id": "deepseek-reasoner",
            "display_name": "DeepSeek Reasoner (R1)",
            "capabilities": ["TEXT_GENERATION", "CODE_REASONING", "MULTILINGUAL"],
            "context_limit": 65536,
            "input_types": ["text"],
            "output_types": ["text"],
            "pricing_per_1k_input": 0.00055,
            "pricing_per_1k_output": 0.00219,
            "latency_class": "slow",
            "quality_class": "premium",
        },
    ],
    "openai": [
        {
            "model_id": "gpt-4o",
            "display_name": "GPT-4o",
            "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                             "VISION", "LONG_CONTEXT", "CODE_REASONING", "MULTILINGUAL"],
            "context_limit": 128000,
            "input_types": ["text", "image"],
            "output_types": ["text", "json"],
            "pricing_per_1k_input": 0.00250,
            "pricing_per_1k_output": 0.01000,
            "latency_class": "fast",
            "quality_class": "premium",
        },
        {
            "model_id": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                             "VISION", "CODE_REASONING", "MULTILINGUAL"],
            "context_limit": 128000,
            "input_types": ["text", "image"],
            "output_types": ["text", "json"],
            "pricing_per_1k_input": 0.00015,
            "pricing_per_1k_output": 0.00060,
            "latency_class": "fast",
            "quality_class": "balanced",
        },
    ],
    "gemini": [
        {
            "model_id": "gemini-2.5-flash",
            "display_name": "Gemini 2.5 Flash",
            "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                             "VISION", "LONG_CONTEXT", "CODE_REASONING", "MULTILINGUAL", "THAI_LANGUAGE"],
            "context_limit": 1048576,
            "input_types": ["text", "image", "document"],
            "output_types": ["text", "json"],
            "pricing_per_1k_input": 0.00015,
            "pricing_per_1k_output": 0.00060,
            "latency_class": "fast",
            "quality_class": "premium",
        },
        {
            "model_id": "gemini-2.5-pro",
            "display_name": "Gemini 2.5 Pro",
            "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                             "VISION", "LONG_CONTEXT", "CODE_REASONING", "MULTILINGUAL"],
            "context_limit": 1048576,
            "input_types": ["text", "image", "document"],
            "output_types": ["text", "json"],
            "pricing_per_1k_input": 0.00125,
            "pricing_per_1k_output": 0.01000,
            "latency_class": "balanced",
            "quality_class": "premium",
        },
    ],
    "anthropic": [
        {
            "model_id": "claude-sonnet-4-20250514",
            "display_name": "Claude Sonnet 4",
            "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                             "VISION", "LONG_CONTEXT", "CODE_REASONING", "MULTILINGUAL"],
            "context_limit": 200000,
            "input_types": ["text", "image"],
            "output_types": ["text", "json"],
            "pricing_per_1k_input": 0.00300,
            "pricing_per_1k_output": 0.01500,
            "latency_class": "balanced",
            "quality_class": "premium",
        },
        {
            "model_id": "claude-3-5-haiku-20241022",
            "display_name": "Claude 3.5 Haiku",
            "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                             "CODE_REASONING", "MULTILINGUAL"],
            "context_limit": 200000,
            "input_types": ["text"],
            "output_types": ["text", "json"],
            "pricing_per_1k_input": 0.00080,
            "pricing_per_1k_output": 0.00400,
            "latency_class": "fast",
            "quality_class": "balanced",
        },
    ],
    "cloudflare": [
        {
            "model_id": "@cf/meta/llama-3-8b-instruct",
            "display_name": "Llama 3 8B (Workers AI)",
            "capabilities": ["TEXT_GENERATION", "FAST_CLASSIFICATION", "MULTILINGUAL"],
            "context_limit": 8192,
            "input_types": ["text"],
            "output_types": ["text"],
            "pricing_per_1k_input": 0.0,  # Free tier
            "pricing_per_1k_output": 0.0,
            "latency_class": "fast",
            "quality_class": "economical",
        },
        {
            "model_id": "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
            "display_name": "DeepSeek R1 Distill Qwen 32B (Workers AI)",
            "capabilities": ["TEXT_GENERATION", "CODE_REASONING", "MULTILINGUAL"],
            "context_limit": 32768,
            "input_types": ["text"],
            "output_types": ["text"],
            "pricing_per_1k_input": 0.0,
            "pricing_per_1k_output": 0.0,
            "latency_class": "slow",
            "quality_class": "balanced",
        },
    ],
}


def _register_default_models(db: Session, provider_code: str, runtime: AIExecutionRuntime, base_url: str = ""):
    """Auto-register known models when an account is created."""
    defaults = _DEFAULT_MODELS.get(provider_code, [])
    for m in defaults:
        model = InstalledModel(runtime_id=runtime.id, **m)
        db.add(model)
