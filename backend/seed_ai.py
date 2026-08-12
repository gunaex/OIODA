"""Seed AI Providers and a test DeepSeek account."""
import sys
sys.path.insert(0, ".")

from app.database import MasterSessionLocal, ensure_master_db
from app.models import AIProvider, AIAccount, AIExecutionRuntime, InstalledModel, AIResource

ensure_master_db()
db = MasterSessionLocal()

# ── Providers ─────────────────────────────────────────
providers = [
    {"code": "deepseek", "name": "DeepSeek", "website": "https://api.deepseek.com",
     "description": "DeepSeek AI — V3 chat + R1 reasoning. OpenAI-compatible API, 64K context, strong multilingual and code capabilities."},
    {"code": "openai", "name": "OpenAI", "website": "https://platform.openai.com",
     "description": "GPT-4o, GPT-4o-mini via official API."},
    {"code": "gemini", "name": "Google Gemini", "website": "https://ai.google.dev",
     "description": "Gemini 1.5/2.0 models via official API."},
    {"code": "anthropic", "name": "Anthropic", "website": "https://api.anthropic.com",
     "description": "Claude 3.5/4 models via official API."},
    {"code": "cloudflare", "name": "Cloudflare Workers AI", "website": "https://developers.cloudflare.com/workers-ai",
     "description": "Serverless GPU inference at the edge."},
    {"code": "local", "name": "Local Runtime", "website": "",
     "description": "Local models via Ollama, vLLM, LM Studio, or desktop GPU."},
]

for p in providers:
    existing = db.query(AIProvider).filter(AIProvider.code == p["code"]).first()
    if not existing:
        db.add(AIProvider(**p))
        print(f"  + Provider: {p['name']} ({p['code']})")
    else:
        print(f"  = Provider exists: {p['name']}")

db.commit()
print("Providers seeded.\n")

# ── Create placeholder DeepSeek account ────────────────
ds = db.query(AIProvider).filter(AIProvider.code == "deepseek").first()
if ds:
    existing = db.query(AIAccount).filter(AIAccount.provider_id == ds.id, AIAccount.name == "DeepSeek — Ready for API Key").first()
    if not existing:
        account = AIAccount(
            provider_id=ds.id,
            name="DeepSeek — Ready for API Key",
            account_type="api",
            access_mode="OFFICIAL_API",
            connector_status="SUPPORTED",
            api_base_url="https://api.deepseek.com",
            api_key_encrypted="",
            api_key_last4="",
            health_state="UNKNOWN",
        )
        db.add(account)
        db.flush()

        runtime = AIExecutionRuntime(
            account_id=account.id,
            runtime_type="OFFICIAL_API",
            endpoint_url="https://api.deepseek.com",
        )
        db.add(runtime)
        db.flush()

        # Register both DeepSeek models
        models = [
            {"model_id": "deepseek-chat", "display_name": "DeepSeek Chat (V3)",
             "capabilities": ["TEXT_GENERATION", "STRUCTURED_OUTPUT", "TOOL_CALLING",
                              "LONG_CONTEXT", "CODE_REASONING", "MULTILINGUAL", "THAI_LANGUAGE"],
             "context_limit": 65536, "pricing_per_1k_input": 0.00027, "pricing_per_1k_output": 0.00110,
             "latency_class": "balanced", "quality_class": "premium"},
            {"model_id": "deepseek-reasoner", "display_name": "DeepSeek Reasoner (R1)",
             "capabilities": ["TEXT_GENERATION", "CODE_REASONING", "MULTILINGUAL"],
             "context_limit": 65536, "pricing_per_1k_input": 0.00055, "pricing_per_1k_output": 0.00219,
             "latency_class": "slow", "quality_class": "premium"},
        ]
        for m in models:
            model = InstalledModel(runtime_id=runtime.id, **m)
            db.add(model)
            db.flush()

            # Auto-create routable resource for each model
            resource = AIResource(
                account_id=account.id,
                runtime_id=runtime.id,
                model_id=model.id,
                display_name=f"DeepSeek — {m['display_name']}",
                entitlements=["SERVER_INFERENCE", "STRUCTURED_OUTPUT", "TOOL_CALLING"],
                allowed_data_classifications=["PUBLIC", "INTERNAL"],
                base_priority=90 if m["model_id"] == "deepseek-chat" else 80,
                max_concurrency=3,
            )
            db.add(resource)
            print(f"  + Resource: {resource.display_name}")

        db.commit()
        print("DeepSeek account + models + resources created.\n")
    else:
        print("DeepSeek account already exists.\n")

# ── Summary ───────────────────────────────────────────
print(f"Providers: {db.query(AIProvider).count()}")
print(f"Accounts:  {db.query(AIAccount).count()}")
print(f"Runtimes:  {db.query(AIExecutionRuntime).count()}")
print(f"Models:    {db.query(InstalledModel).count()}")
print(f"Resources: {db.query(AIResource).count()}")

db.close()
print("\nDone!")
