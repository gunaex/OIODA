"""
Cloudflare Turnstile Integration
Server-side verification of Turnstile tokens for abuse-sensitive flows.
"""

import os

import httpx

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Test keys always pass verification
_IS_TEST_KEY = TURNSTILE_SECRET_KEY.startswith("1x0000") or TURNSTILE_SECRET_KEY.startswith("2x0000")


async def verify_turnstile(token: str, remote_ip: str = "") -> dict:
    """Verify a Turnstile token server-side.

    Returns:
        {"success": bool, "error_codes": list, ...}
    """
    if not token:
        return {"success": False, "error_codes": ["missing-input"]}

    # Test keys always pass (for development/testing)
    if _IS_TEST_KEY:
        return {"success": True, "challenge_ts": "test", "hostname": "test"}

    async with httpx.AsyncClient(timeout=10) as client:
        form_data = {
            "secret": TURNSTILE_SECRET_KEY,
            "response": token,
        }
        if remote_ip:
            form_data["remoteip"] = remote_ip

        try:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=form_data)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"success": False, "error_codes": [f"verification-failed: {str(e)}"]}


def requires_turnstile(protected: bool = True):
    """Dependency: validates Turnstile token from request header.

    Usage:
        @router.post("/sensitive-endpoint")
        async def endpoint(token_valid: bool = Depends(requires_turnstile())):
            ...
    """
    async def _verify(request=None):
        if not protected:
            return True

        # In test/dev mode with test key, always pass
        if _IS_TEST_KEY:
            return True

        # Get token from header
        token = None
        if request:
            token = request.headers.get("X-Turnstile-Token", "")

        if not token:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Turnstile token required")

        result = await verify_turnstile(token)
        if not result.get("success"):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Turnstile verification failed")

        return True

    return _verify


TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "1x00000000000000000000AA")
