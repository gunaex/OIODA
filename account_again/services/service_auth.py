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

import time
import uuid
from typing import Optional
from jose import jwt, JWTError
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

ISSUER = "account-again-local"
AUDIENCE = "again-ecosystem-services"
TOKEN_TTL_SECONDS = 300
ALGORITHM = "RS256"

# Ephemeral runtime-generated RSA keypair (E5.1 §18: "generate ephemeral runtime keys...
# never commit production-like private keys"). Regenerated on every process start —
# tokens do not survive a restart, which is the correct behavior for a dev-mode issuer
# with no persistence story of its own.
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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

_KEY_ID = "account-again-local-1"


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
