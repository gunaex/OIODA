"""Account Again — Secret resolver (runtime boundary, NOT a secret-value database).

E5 formalizes this into an interface (SecretResolverBase) with environment-specific
implementations, per the target ownership model:

    Account Again    -> owns credentialRef metadata + authorization (unchanged)
    Secret Store      -> owns the actual secret value (this module's job)
    Local AI Control  -> transient consumer (unchanged, see CredentialResolverClient)
    Center / adapter

Secret values exist only transiently — never persisted to this app's DB, never emitted
in events, never returned by any endpoint except the one dedicated resolve() boundary
(POST /credential-refs/{ref}/resolve, E4-C).
"""

import os
from abc import ABC, abstractmethod
from typing import Optional


class SecretResolverBase(ABC):
    """Interface every environment-specific secret resolver implements.

    E5 §37: different deployment zones may need different implementations (local dev
    reads env vars; a cloud deployment might use 1Password Connect, HashiCorp Vault,
    Cloudflare/Fly secrets, or a cloud provider's own secret manager) — but the calling
    code (the /credential-refs/{ref}/resolve endpoint) is written against this interface
    only, so swapping the backing store never touches API/domain logic.
    """

    @abstractmethod
    def resolve(self, credential_ref: str, provider: str, purpose: str) -> Optional[str]:
        """Resolve a credential reference to its secret value.

        Returns None if the credential cannot be resolved. The secret value must NOT be
        logged, stored, or returned in any API response other than the dedicated resolve
        boundary's response.
        """
        raise NotImplementedError


class EnvSecretResolver(SecretResolverBase):
    """Development-mode resolver: reads from environment variables.

    Maps credential_ref + provider -> {PROVIDER}_API_KEY, with a direct
    CREDENTIAL_{ref} override for cases where no provider-shaped env var applies.
    This is the resolver Account Again actually runs today, unchanged in shape since E3
    — E5 only extracted the interface around it, it did not change its behavior.
    """

    def resolve(self, credential_ref: str, provider: str, purpose: str) -> Optional[str]:
        env_var = f"{provider.upper()}_API_KEY"
        value = os.getenv(env_var)
        if value:
            return value
        return os.getenv(f"CREDENTIAL_{credential_ref.upper()}")


class StaticMapSecretResolver(SecretResolverBase):
    """Production-like adapter SHAPE — demonstrates what a real external secret-store
    adapter (1Password Connect, HashiCorp Vault, a cloud provider's Secret Manager)
    would look like structurally: constructed with connection details, resolves by
    looking up an opaque reference in an external store rather than a local env var.

    This implementation backs the "external store" with an in-memory map instead of a
    real network call — there is no Vault/1Password instance available in this
    environment to integrate against honestly, and installing one is out of scope for
    E5 (task §66: "do not spend E5 implementing every platform feature"). A genuine
    HTTP-based implementation (e.g. VaultSecretResolver making a real GET to
    {vault_addr}/v1/secret/data/{ref}) would follow the exact same resolve() signature —
    swapping this class for one is the only change required, by design.
    """

    def __init__(self, store: Optional[dict] = None):
        self._store = store or {}

    def put(self, credential_ref: str, secret: str) -> None:
        """Test/setup helper — not part of the interface, not used by production code."""
        self._store[credential_ref] = secret

    def resolve(self, credential_ref: str, provider: str, purpose: str) -> Optional[str]:
        return self._store.get(credential_ref)


def _select_resolver() -> SecretResolverBase:
    mode = os.getenv("ACCOUNT_AGAIN_SECRET_RESOLVER", "env")
    if mode == "static_map":
        return StaticMapSecretResolver()
    return EnvSecretResolver()


# Singleton — selection driven by ACCOUNT_AGAIN_SECRET_RESOLVER (config.py already
# reads this env var; E5 makes the selection real instead of documentation-only).
secret_resolver: SecretResolverBase = _select_resolver()
