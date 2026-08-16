"""Account Again — LOCAL_OIDC_COMPATIBLE_SERVICE_AUTH (E5.1).

Smallest production-shaped local equivalent of OAuth2/OIDC client-credentials service
authentication, using a standard JWT library (python-jose) — no custom cryptography.

Honest naming: this is NOT enterprise OIDC. There is no external IdP, no key rotation
policy, no revocation list beyond the existing ServiceIdentity.status check performed on
every request (never trust token validity alone — see verify_and_load_service_identity
in api/routes.py). It is a real, standards-shaped (RS256 JWT, iss/sub/aud/iat/exp/jti
claims) local mechanism that replaces the E4.1 LOCAL_TRUSTED_SERVICE_CONTEXT header as
the actual authorization input, while that header remains for correlation/debug only.

TOKEN_ISSUER:              account-again-local
TOKEN_AUDIENCE:             again-ecosystem-services
SERVICE_SUBJECT_MAPPING:    JWT `sub` = ServiceIdentity.service_identity_id
TOKEN_TTL:                  300 seconds (short-lived, matches "authorization caching"
                             guidance in E5 — no long-lived trust)
REVOCATION_BEHAVIOR:        token signature/expiry alone is NOT sufficient — every
                             protected endpoint re-checks ServiceIdentity.status in the
                             DB on every request; a revoked service identity is denied
                             even with an unexpired, correctly-signed token.
"""

import base64
import hashlib
import os
import time
import uuid
from typing import Optional
from jose import jwt, JWTError
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

ISSUER = os.getenv("ACCOUNT_AGAIN_ISSUER", "account-again-local")
AUDIENCE = os.getenv("ACCOUNT_AGAIN_AUDIENCE", "again-ecosystem-services")
CONFIRMATION_AUDIENCE = "again-ecosystem-confirmation"
CONFIRMATION_TTL_SECONDS = 300
TOKEN_TTL_SECONDS = 300
# Ecosystem human identity token — the SSO credential downstream bounded
# services accept. Longer-lived than a confirmation token but still short-lived
# (1h) so a leaked token expires quickly; services re-check account status on
# every request, never trusting signature/expiry alone.
ECOSYSTEM_IDENTITY_AUDIENCE = "again-ecosystem-identity"
ECOSYSTEM_IDENTITY_TTL_SECONDS = 3600
ALGORITHM = "RS256"

# Signing key loading (R2A deployment):
#   - If ACCOUNT_AGAIN_SIGNING_KEY_B64 is set (Fly secret): load the persistent
#     PKCS8 PEM RSA private key from base64. Production path — the key survives
#     restarts, so issued tokens and the published JWKS stay consistent.
#   - Otherwise: generate an ephemeral runtime RSA keypair (E5.1 §18). Dev-mode path —
#     regenerated on every process start, so tokens do not survive a restart, which is
#     correct for a local dev issuer with no persistence story of its own.
# A configured key MUST parse or the process fails closed at import time — it never
# silently falls back to an ephemeral key in production (which would rotate the signing
# identity and break every in-flight verification).
_ENV_KEY_B64 = os.getenv("ACCOUNT_AGAIN_SIGNING_KEY_B64")
_ENV_KEY_ID = os.getenv("ACCOUNT_AGAIN_SIGNING_KEY_ID")


def _load_private_key():
    if _ENV_KEY_B64:
        try:
            pem_bytes = base64.b64decode(_ENV_KEY_B64)
            return serialization.load_pem_private_key(pem_bytes, password=None)
        except Exception as e:
            raise RuntimeError(
                "ACCOUNT_AGAIN_SIGNING_KEY_B64 is set but cannot be loaded as a "
                f"PKCS8 PEM private key: {e}"
            ) from e
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


_private_key = _load_private_key()
_public_key = _private_key.public_key()

_PRIVATE_PEM = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
_PUBLIC_PEM = _public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)


def _derive_kid() -> str:
    """Stable key id. Explicit env override wins; for a persistent key the kid is a
    fingerprint of the public key so it is identical across restarts."""
    if _ENV_KEY_ID:
        return _ENV_KEY_ID
    if _ENV_KEY_B64:
        der = _public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return "account-again-" + hashlib.sha256(der).hexdigest()[:12]
    return "account-again-local-1"


_KEY_ID = _derive_kid()


class ServiceTokenError(Exception):
    """Raised for any invalid/expired/malformed token — callers map this to 401."""


def issue_service_token(*, service_identity_id: str, system_id: str, tenant_id: Optional[str]) -> dict:
    """Issue a short-lived signed JWT for a verified service identity.

    Caller (the /auth/service-token route) is responsible for verifying the client
    secret BEFORE calling this — this function does not authenticate, only issues.
    """
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": service_identity_id,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        "jti": str(uuid.uuid4()),
        "systemId": system_id,
        "serviceIdentityId": service_identity_id,
        "tenantId": tenant_id,
    }
    token = jwt.encode(claims, _PRIVATE_PEM, algorithm=ALGORITHM, headers={"kid": _KEY_ID})
    return {"accessToken": token, "tokenType": "Bearer", "expiresIn": TOKEN_TTL_SECONDS, "claims": claims}


def verify_service_token(token: str) -> dict:
    """Verify signature, issuer, audience, and expiry. Returns the claim set on success.

    Does NOT check ServiceIdentity.status — token cryptographic validity is necessary
    but not sufficient; the caller must separately re-check the DB (E5.1 §10).
    """
    try:
        claims = jwt.decode(token, _PUBLIC_PEM, algorithms=[ALGORITHM], audience=AUDIENCE, issuer=ISSUER)
    except JWTError as e:
        raise ServiceTokenError(str(e)) from e
    if "systemId" not in claims or "serviceIdentityId" not in claims:
        raise ServiceTokenError("token missing required claims")
    return claims


def issue_confirmation_token(*, subject_id: str, account_id: str, tenant_id: Optional[str], purpose: str = "document-again-confirm") -> dict:
    """Issue a short-lived human confirmation token after a successful password
    re-authentication. Distinct audience from service tokens so a service token
    can never be replayed as an admin confirmation."""
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": subject_id,
        "aud": CONFIRMATION_AUDIENCE,
        "iat": now,
        "exp": now + CONFIRMATION_TTL_SECONDS,
        "jti": str(uuid.uuid4()),
        "accountId": account_id,
        "tenantId": tenant_id,
        "purpose": purpose,
    }
    token = jwt.encode(claims, _PRIVATE_PEM, algorithm=ALGORITHM, headers={"kid": _KEY_ID})
    return {
        "confirmationToken": token,
        "tokenType": "Bearer",
        "expiresIn": CONFIRMATION_TTL_SECONDS,
        "claims": claims,
    }


def verify_confirmation_token(token: str) -> dict:
    """Verify a human confirmation token's signature, audience, issuer, expiry and
    required claims. Never contains the password — the password is checked once at
    issuance and discarded."""
    try:
        claims = jwt.decode(
            token, _PUBLIC_PEM, algorithms=[ALGORITHM],
            audience=CONFIRMATION_AUDIENCE, issuer=ISSUER,
        )
    except JWTError as e:
        raise ServiceTokenError(str(e)) from e
    if "accountId" not in claims or "purpose" not in claims:
        raise ServiceTokenError("confirmation token missing required claims")
    return claims


def issue_ecosystem_identity_token(*, account_id: str, subject_id: str, tenant_id: Optional[str], email: str, ecosystem_roles: list[str]) -> dict:
    """Issue the short-lived ecosystem human identity token (SSO). The password
    is checked once by the caller before this function is invoked; it is never
    embedded here. Claims carry a stable subject (account_id) and email only as
    profile data — downstream services map by account_id, not email."""
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": account_id,
        "aud": ECOSYSTEM_IDENTITY_AUDIENCE,
        "iat": now,
        "exp": now + ECOSYSTEM_IDENTITY_TTL_SECONDS,
        "jti": str(uuid.uuid4()),
        "accountId": account_id,
        "subjectId": subject_id,
        "tenantId": tenant_id,
        "email": email,
        "ecosystemRoles": ecosystem_roles,
    }
    token = jwt.encode(claims, _PRIVATE_PEM, algorithm=ALGORITHM, headers={"kid": _KEY_ID})
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresIn": ECOSYSTEM_IDENTITY_TTL_SECONDS,
        "claims": claims,
    }


def verify_ecosystem_identity_token(token: str) -> dict:
    """Verify an ecosystem human identity token's signature, audience, issuer
    and expiry. Signature validity is necessary but not sufficient — callers
    must still resolve the account status / service-local authorization."""
    try:
        claims = jwt.decode(
            token, _PUBLIC_PEM, algorithms=[ALGORITHM],
            audience=ECOSYSTEM_IDENTITY_AUDIENCE, issuer=ISSUER,
        )
    except JWTError as e:
        raise ServiceTokenError(str(e)) from e
    if "sub" not in claims or "accountId" not in claims:
        raise ServiceTokenError("ecosystem identity token missing required claims")
    return claims


def get_jwks() -> dict:
    """Public-key verification endpoint shape (E5.1 §19) — not a full IdP product,
    just enough for a caller to independently verify tokens if it wanted to."""
    public_numbers = _public_key.public_numbers()

    def _b64url_uint(n: int) -> str:
        import base64
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": ALGORITHM,
                "kid": _KEY_ID,
                "n": _b64url_uint(public_numbers.n),
                "e": _b64url_uint(public_numbers.e),
            }
        ]
    }
