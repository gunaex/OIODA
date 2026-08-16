from fastapi import HTTPException, Request

from . import account_again_client
from .account_again_client import ServiceAuthError

# The only system id QA Again currently trusts to dispatch a QARequest.
CONDUCTOR_SYSTEM_ID = "CONDUCTOR_MAIN"


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :]
    return None


def require_conductor_service_identity(request: Request) -> dict:
    """FastAPI dependency: verifies the inbound request carries a valid
    Account-Again-issued service token for CONDUCTOR_MAIN. Fail-closed on
    every path — missing token is 401, invalid/wrong-system token is 403,
    never a silent pass-through. The caller's claimed identity (headers,
    body fields) is never trusted on its own (SERVICE_IDENTITY_SPOOF_BLOCKED)."""
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Conductor service token")

    try:
        claims = account_again_client.verify_service_token(token)
    except ServiceAuthError as exc:
        raise HTTPException(status_code=403, detail=f"Invalid Conductor service token: {exc}") from exc

    system_id = claims.get("systemId")
    if system_id != CONDUCTOR_SYSTEM_ID:
        raise HTTPException(status_code=403, detail=f"Service identity {system_id!r} is not permitted to dispatch work here")

    return claims
