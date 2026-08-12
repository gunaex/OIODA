"""
Conductor Again — Rate Limiting
Uses slowapi, 100 requests/minute default.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
