# INFRA-AGAIN M4.2 — REAL OPENAI ACCEPTANCE RETRY
# FINAL REPORT
# Date: 2026-08-11

======================================================================
EXECUTIVE SUMMARY
======================================================================

M4.2 real cloud acceptance could NOT proceed.

The OPENAI_API_KEY in the environment returns HTTP 401 with error:
  "Your API key has been invalidated." (code: token_invalidated)

This is the SAME key from M4.1 that previously returned
credit_balance_exhausted. The key has since been explicitly invalidated.

The user stated a new key is configured, but the environment variable
still holds the old invalidated key. A new export is required.

FINAL_STATUS=BLOCKED_KEY_INVALIDATED

======================================================================
TEST RESULTS
======================================================================

UNIT + CONTRACT:  79 passed, 3 failed

The 3 failures are exclusively the real OpenAI cloud tests:
  test_cloud_generation_patient_portal  ❌ FAIL (HTTP 401 token_invalidated)
  test_cloud_refine_ecs_fargate         ❌ FAIL (HTTP 401 token_invalidated)
  test_cloud_refine_add_redis           ❌ FAIL (HTTP 401 token_invalidated)

All non-cloud tests pass:
  M3_ROUTER_TESTS=     PASS (14/14)
  CLOUD_VALIDATION_ENFORCED=        PASS
  CLOUD_FAILURE_NO_SILENT_FALLBACK= PASS
  CLOUD_POLICY_BLOCK=               PASS
  PROVENANCE_COMPLETE=              PASS
  TOKEN_USAGE_CAPTURED=             PASS

UI_TYPECHECK=          PASS (no errors)
UI_BUILD=              PASS (1.01s)
INTEGRATION=           107/115 PASS (8 pre-existing OpenTofu failures)

======================================================================
BLOCKER
======================================================================

The current OPENAI_API_KEY returns:
  HTTP 401 — "Your API key has been invalidated." (token_invalidated)

Resolution:
  Export the new API key in the terminal:
    export OPENAI_API_KEY="sk-..."  (the NEW key with credits)
    export AGAINPILOT_ROUTER_MODE="HYBRID"

Then re-run:
  PYTHONPATH=src INFRA_AGAIN_DB=/tmp/app.db .venv/bin/python \
    -m pytest tests/unit/test_m4_cloud.py -v \
    -k "cloud_generation or cloud_refine"

======================================================================
FINAL REPORT CARD
======================================================================

CLOUD_PROVIDER=            OPENAI
CLOUD_MODEL=               gpt-4o

REAL_OPENAI_GENERATION=    BLOCKED (HTTP 401 token_invalidated)
REAL_OPENAI_REFINE_ECS=    BLOCKED (HTTP 401 token_invalidated)
REAL_OPENAI_REFINE_REDIS=  BLOCKED (HTTP 401 token_invalidated)

GENERATION_QUALITY=        DEFERRED
GENERATION_COMPLETENESS=   DEFERRED

ECS_DELTA_NON_EMPTY=       DEFERRED
ECS_APP_RUNTIMES=          DEFERRED
ECS_DB_PRIVATE=            DEFERRED

REDIS_PRESENT=             DEFERRED
REDIS_DELTA_NON_EMPTY=     DEFERRED

CLOUD_REFINE_BROWSER=      DEFERRED
CLOUD_APPLY_BROWSER=       DEFERRED
CLOUD_DRAWIO_REFRESH=      DEFERRED

INPUT_TOKENS=              N/A
OUTPUT_TOKENS=             N/A

M3_ROUTER_TESTS=           PASS (14/14)
UNIT_CONTRACT=             79/82 PASS (3 cloud blocked)
UI_TYPECHECK=              PASS
UI_BUILD=                  PASS

FINAL_STATUS=              BLOCKED_KEY_INVALIDATED

======================================================================
HISTORY
======================================================================

M4.0:  IMPLEMENTED_NOT_VERIFIED       (no API key)
M4.1:  IMPLEMENTED_BLOCKED_BY_BILLING (credit_balance_exhausted)
M4.2:  BLOCKED_KEY_INVALIDATED        (token_invalidated)

Next:  HYBRID_CLOUD_AI_VERIFIED       (after new key + all 3 cloud tests pass)
