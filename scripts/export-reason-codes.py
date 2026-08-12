#!/usr/bin/env python3
"""Export the canonical entitlement reason-code vocabulary as JSON.

entitlement_engine.REASON_CODES is the single source of truth (E4.1 §6). This script
exists so AGAIN-ECOSYSTEM's contract-reconciliation tooling can diff the canonical v2
schema's reasonCode enum against actual runtime codes without importing Python types
across repos.

Usage:
    python3 scripts/export-reason-codes.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from account_again.services.entitlement_engine import REASON_CODES

print(json.dumps(sorted(REASON_CODES), indent=2))
