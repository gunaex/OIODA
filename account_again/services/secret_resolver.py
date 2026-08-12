"""Account Again — Secret resolver (runtime boundary, NOT a secret-value database)."""

import os
from typing import Optional


class SecretResolver:
    """Resolves credential references to secret values at runtime.
    
    Secret values exist only transiently — never persisted to DB,
    never emitted in events, never returned by normal APIs.
    
    Development mode: reads from environment variables.
    Production: must use a proper secret store (E5 concern).
    """

    def resolve(self, credential_ref: str, provider: str, purpose: str) -> Optional[str]:
        """Resolve a credential reference to its secret value.
        
        Returns None if the credential cannot be resolved.
        The secret value must NOT be logged, stored, or returned in API responses.
        """
        # Development mode: map credential_ref + provider to env var
        # E.g., credential_ref "abc123" + provider "openai" → OPENAI_API_KEY
        env_var = f"{provider.upper()}_API_KEY"
        value = os.getenv(env_var)
        if value:
            return value
        # Alternative: direct ref lookup
        value = os.getenv(f"CREDENTIAL_{credential_ref.upper()}")
        return value


# Singleton
secret_resolver = SecretResolver()
