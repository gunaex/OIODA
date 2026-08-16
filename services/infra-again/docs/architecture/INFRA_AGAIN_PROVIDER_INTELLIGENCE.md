# INFRA-AGAIN Provider Intelligence Model

## Architecture

```
Official Provider Sources (AWS APIs, GCP APIs)
        ↓
Catalog Synchronizer (per-provider)
        ↓
Raw Provider Metadata (versioned, checksummed)
        ↓
Normalization / Classification
        ↓
Dynamic Capability Registry
        ↓
Capability Mapper
        ↓
Provider-Neutral Planner + AI Reasoning
```

## Key Principle

```
✅ Official Provider Data → Capability Registry → AI Reasoning
❌ LLM Memory → Infrastructure Execution
```

The LLM is NOT the authoritative cloud catalog.

## Components

1. **Catalog Synchronizer** — Pulls official data on schedule
2. **Capability Mapper** — Maps neutral intent to provider resources
3. **Dynamic Capability Registry** — Central store with lifecycle tracking
4. **Change Detection** — Diffs between catalog versions
5. **Provenance** — Every entry traces to source API

## Catalog Snapshot

Every sync produces a versioned snapshot:
- Timestamp, provider, API version
- Content checksum
- Diff from previous version
