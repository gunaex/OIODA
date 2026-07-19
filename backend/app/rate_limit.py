from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared Limiter instance — imported by main.py (to register the exception
# handler + default limit) and by routers that need a stricter limit on a
# specific endpoint (login).
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
