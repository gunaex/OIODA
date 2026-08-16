"""Outbound ecosystem delivery client (Document Again -> downstream hop).

Document Again holds the DOCUMENT_AGAIN service identity (issued by Account
Again). It delivers versioned ecosystem payloads to the configured downstream
URL with an Idempotency-Key (the event correlation id) and X-Tenant-Id header,
failing closed on any transport or non-2xx response.

Authority boundary: PM Again and QA Again only accept the CONDUCTOR_MAIN
service identity (their intake verifies systemId == "CONDUCTOR_MAIN" against
Account Again's JWKS). Document Again must therefore deliver handoffs to the
ecosystem orchestrator (Conductor Main) rather than impersonate it. See
docs/P4_ECOSYSTEM_INTEGRATION.md for the exact contract gap.
"""
from __future__ import annotations

import os

import httpx

from .account_client import ACCOUNT_AGAIN_PREFIX, ACCOUNT_AGAIN_URL, SERVICE_SYSTEM_ID

DELIVERY_TIMEOUT = float(os.environ.get("ECOSYSTEM_DELIVERY_TIMEOUT", "15.0"))
DOCUMENT_AGAIN_CLIENT_SECRET = os.environ.get("DOCUMENT_AGAIN_CLIENT_SECRET", "")


class DeliveryError(Exception):
    """Raised when outbound delivery cannot succeed. Callers fail closed."""


class EcosystemDeliveryClient:
    def __init__(
        self,
        account_again_url: str | None = None,
        client_secret: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.account_again_url = (account_again_url or ACCOUNT_AGAIN_URL).rstrip("/")
        self.client_secret = client_secret or DOCUMENT_AGAIN_CLIENT_SECRET
        self._transport = transport
        self._token: str | None = None

    def _client(self) -> httpx.Client:
        kwargs = {"timeout": DELIVERY_TIMEOUT}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def service_token(self) -> str:
        """Obtain (and cache) an Account Again service token for DOCUMENT_AGAIN."""
        if self._token:
            return self._token
        if not self.account_again_url:
            raise DeliveryError("ACCOUNT_AGAIN_URL is not configured")
        if not self.client_secret:
            raise DeliveryError("DOCUMENT_AGAIN_CLIENT_SECRET is not configured")
        try:
            with self._client() as c:
                resp = c.post(
                    f"{self.account_again_url}{ACCOUNT_AGAIN_PREFIX}/auth/service-token",
                    json={"systemId": SERVICE_SYSTEM_ID, "clientSecret": self.client_secret},
                )
        except httpx.HTTPError as exc:
            raise DeliveryError(f"Account Again unreachable for token: {exc}") from exc
        if resp.status_code != 200:
            raise DeliveryError(f"Account Again rejected service-token request: {resp.status_code}")
        self._token = resp.json()["accessToken"]
        return self._token

    def deliver(
        self, url: str, payload: dict, *, correlation_id: str, tenant_id: str | None = None
    ) -> str | None:
        """POST a versioned payload to a downstream URL, idempotently.

        Returns the downstream external reference id on success (the value of
        ``externalWorkReferenceId`` / ``externalReferenceId`` / ``id`` in the
        JSON response, whichever is present), or None if the response carries
        no reference.
        """
        headers = {
            "Authorization": f"Bearer {self.service_token()}",
            "Idempotency-Key": correlation_id,
        }
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        try:
            with self._client() as c:
                resp = c.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise DeliveryError(f"Delivery unreachable: {exc}") from exc
        if resp.status_code == 409:
            raise DeliveryError("Downstream reported an idempotency conflict")
        if resp.status_code >= 400:
            raise DeliveryError(f"Downstream rejected delivery: {resp.status_code} {resp.text[:200]}")
        try:
            body = resp.json()
        except Exception:
            body = {}
        return body.get("externalWorkReferenceId") or body.get("externalReferenceId") or body.get("id")


delivery_client = EcosystemDeliveryClient()
