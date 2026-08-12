"""Account Again — E5 secret resolver interface + adapter tests.

Proves the SecretResolverBase interface has (at least) one development adapter
(EnvSecretResolver, unchanged behavior from E3/E4) and one production-like adapter
shape (StaticMapSecretResolver, standing in for an external store like Vault/1Password
since none is available in this environment — see secret_resolver.py docstring).
"""

from account_again.services.secret_resolver import (
    SecretResolverBase, EnvSecretResolver, StaticMapSecretResolver,
)


class TestEnvSecretResolver:
    def test_resolves_from_provider_env_var(self, monkeypatch):
        monkeypatch.setenv("E5TESTPROVIDER_API_KEY", "dummy-dev-secret-not-real")
        resolver = EnvSecretResolver()
        assert resolver.resolve("ref-1", "e5testprovider", "test") == "dummy-dev-secret-not-real"

    def test_resolves_from_direct_credential_override(self, monkeypatch):
        monkeypatch.delenv("UNKNOWNPROVIDER_API_KEY", raising=False)
        monkeypatch.setenv("CREDENTIAL_REF-XYZ", "dummy-direct-secret-not-real")
        resolver = EnvSecretResolver()
        assert resolver.resolve("ref-xyz", "unknownprovider", "test") == "dummy-direct-secret-not-real"

    def test_unresolvable_returns_none(self, monkeypatch):
        monkeypatch.delenv("NOPROVIDER_API_KEY", raising=False)
        monkeypatch.delenv("CREDENTIAL_NOPE", raising=False)
        resolver = EnvSecretResolver()
        assert resolver.resolve("nope", "noprovider", "test") is None

    def test_is_instance_of_base_interface(self):
        assert isinstance(EnvSecretResolver(), SecretResolverBase)


class TestStaticMapSecretResolver:
    """Stands in for a production-like external secret store adapter."""

    def test_resolves_seeded_secret(self):
        resolver = StaticMapSecretResolver()
        resolver.put("ref-1", "dummy-vault-secret-not-real")
        assert resolver.resolve("ref-1", "anyprovider", "test") == "dummy-vault-secret-not-real"

    def test_unresolvable_returns_none(self):
        resolver = StaticMapSecretResolver()
        assert resolver.resolve("nope", "anyprovider", "test") is None

    def test_is_instance_of_base_interface(self):
        assert isinstance(StaticMapSecretResolver(), SecretResolverBase)

    def test_isolated_stores_do_not_leak_between_instances(self):
        r1 = StaticMapSecretResolver()
        r2 = StaticMapSecretResolver()
        r1.put("ref-1", "secret-only-in-r1")
        assert r2.resolve("ref-1", "p", "test") is None
