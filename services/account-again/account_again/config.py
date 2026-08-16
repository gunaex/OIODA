"""Account Again — Configuration."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv(
    "ACCOUNT_AGAIN_DATABASE_URL",
    f"sqlite:///{BASE_DIR}/account_again.db",
)

# Secret resolution: development-only env-var resolver
# Production must use a proper secret store (E5 concern)
SECRET_RESOLVER_MODE = os.getenv("ACCOUNT_AGAIN_SECRET_RESOLVER", "env")

# API settings
API_PREFIX = "/api/v1"
PROJECT_NAME = "Account Again"
VERSION = "1.0.0"
