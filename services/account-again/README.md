# Account Again

**Identity / Access / Credential / AI Entitlement Control Plane** for the AGAIN Ecosystem.

## Role

Account Again is the authoritative owner of:
- User / Account identity
- Tenant / Organization
- Authentication identity & session metadata
- Role-based access control (RBAC)
- Product entitlements
- AI provider/model/capability entitlements
- Credential reference management (metadata only — NO raw secrets in DB)
- Service identity for inter-system communication
- Audit trail
- Quota / budget policy
- Usage recording

## What Account Again Is NOT

- NOT a shared application database
- NOT a business orchestrator (Conductor Main's role)
- NOT an AI execution engine (Local AI Control Center's role)
- NOT a model router
- NOT a secret-value database
- NOT a generic configuration junk drawer

## Critical Rules

- NO RAW API KEY IN AGAIN EVENT
- NO RAW AI KEY IN DOMAIN DATABASE
- NO RAW PASSWORD IN DOMAIN DATABASE BEYOND PROPER HASHED AUTH MATERIAL
- NO SHARED LOGIN DATABASE BETWEEN AGAIN APPS
- NO APP-SPECIFIC AI ACCOUNT SILOS AS TARGET STATE

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Migrate (local SQLite)
alembic upgrade head

# Run
uvicorn account_again.main:app --reload --port 8001

# Test
pytest tests/ -v
```

## API

See `account_again/api/` for route definitions.

## Architecture

See `docs/architecture/ACCOUNT_AGAIN_ARCHITECTURE.md` in the AGAIN-ECOSYSTEM repository.
