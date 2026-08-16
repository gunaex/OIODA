"""
Conductor Again — Rate Limiting
Uses slowapi, 100 requests/minute default.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Disabled under pytest (conftest.py sets TESTING=true): the TestClient shares one
# remote address across every test, so per-route limits like login's 10/minute
# exhaust after a handful of tests and fail unrelated fixtures with 429s — a
# pre-existing E7-documented test-infrastructure issue, not a functional rate-limit
# bug. Production/dev server runs are unaffected.
limiter = Limiter(
    key_func=get_remote_address, default_limits=["100/minute"],
    enabled=os.getenv("TESTING") != "true",
)
