"""Seed AI providers, accounts, and resources after DB reset."""
import requests, json

BASE = "http://127.0.0.1:8000/api"

# Login
r = requests.post(f"{BASE}/auth/login", json={
    "email": "admin@conductoragain.local",
    "password": "ChangeMe123!",
})
h = {"Authorization": "Bearer " + r.json()["access_token"]}
print("Logged in")

# Seed providers
providers = [
    ("deepseek", "DeepSeek", "https://deepseek.com"),
    ("openai", "OpenAI", "https://openai.com"),
    ("gemini", "Google Gemini", "https://ai.google.dev"),
    ("anthropic", "Anthropic", "https://anthropic.com"),
    ("cloudflare", "Cloudflare Workers AI", "https://developers.cloudflare.com/workers-ai"),
]
provider_ids = {}
for code, name, website in providers:
    r = requests.post(f"{BASE}/ai/providers", headers=h, json={
        "code": code, "name": name, "website": website,
    })
    if r.status_code == 201:
        pid = r.json()["id"]
        provider_ids[code] = pid
        print(f"  Provider {code}: {pid[:8]}")
    else:
        # Might already exist
        r2 = requests.get(f"{BASE}/ai/providers", headers=h)
        for p in r2.json():
            if p["code"] == code:
                provider_ids[code] = p["id"]
                print(f"  Provider {code}: {p['id'][:8]} (existing)")
                break

# Add DeepSeek Account with API key (use env or placeholder)
import os
ds_key = os.getenv("DEEPSEEK_API_KEY", "")
if not ds_key:
    print("WARNING: No DEEPSEEK_API_KEY set. Using placeholder.")
    ds_key = "sk-placeholder"

r = requests.post(f"{BASE}/ai/accounts", headers=h, json={
    "provider_id": provider_ids["deepseek"],
    "name": "DeepSeek Main",
    "account_type": "api",
    "access_mode": "OFFICIAL_API",
    "api_key": ds_key,
    "api_base_url": "https://api.deepseek.com",
})
if r.status_code == 201:
    print(f"DeepSeek account: {r.json()['id'][:8]}")
else:
    print(f"DeepSeek account FAILED: {r.status_code} {r.text[:200]}")

# Show resources
r = requests.get(f"{BASE}/ai/pool-summary", headers=h)
print(f"Pool: {json.dumps(r.json())}")
