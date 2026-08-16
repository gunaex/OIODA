# INFRA-AGAIN Capability Model

## Capability Categories

| Category | Examples |
|---|---|
| COMPUTE | Containers, VMs, serverless |
| DATABASE | PostgreSQL, MySQL, MongoDB |
| STORAGE | Object, block, file |
| NETWORKING | Load balancer, DNS, CDN |
| CONTAINER | Kubernetes, ECS, GKE |
| SECURITY | IAM, KMS, secrets |
| OBSERVABILITY | Logging, monitoring, tracing |
| MESSAGING | Queue, pub/sub, event bus |

## Capability Lifecycle

```
DISCOVERED
    ↓
METADATA_COLLECTED
    ↓
CAPABILITY_MAPPED
    ↓
SCHEMA_VALIDATED
    ↓
EXECUTION_SUPPORT_CHECKED
    ↓
VERIFIED
    ↓
SUPPORTED
```

Also tracked:
- UNVERIFIED — Discovered but not validated
- UNAVAILABLE — Not in target region
- DEPRECATED — Still functional, planned removal
- RETIRED — No longer available

## Critical Rule

```
DISCOVERED != SUPPORTED != SAFE_TO_EXECUTE
```

## Provider-Neutral Intent

Correct (provider-neutral):
```yaml
database:
  engine: postgresql
  availability: production
  backup: required
```

Incorrect (provider-specific):
```yaml
database:
  aws_rds_instance: db.r6g.large
```
