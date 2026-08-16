"""
Shared service-identity health check (ECOSYSTEM-H1).

HTTP 200 alone is not proof of *which* service answered — two local dev
services can share a port during misconfiguration (e.g. PM Again and QA
Again both defaulting to :8000) and a bare status-code check would report
the wrong one as healthy. This helper requires the response body to also
carry the expected `service` identity field, so a mismatched service
fails closed instead of being silently accepted as reachable.
"""

import httpx


def check_service_identity(url: str, *, expected_service: str, timeout: float) -> bool:
    """Returns True only if `url` responds 200 with a JSON body whose
    "service" field equals expected_service. Any transport failure,
    non-200 status, unparsable body, or identity mismatch fails closed
    (returns False) — never an implicit healthy."""
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.HTTPError:
        return False
    if resp.status_code != 200:
        return False
    try:
        body = resp.json()
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("service") == expected_service
