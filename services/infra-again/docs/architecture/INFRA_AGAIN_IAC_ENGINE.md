# INFRA-AGAIN IaC Engine Model

## Role

INFRA-AGAIN owns intent, planning, orchestration, safety, evidence, and observed state.
The IaC engine (OpenTofu) owns IaC execution state.

```
Infrastructure Again  ≠  OpenTofu

Infrastructure Again  =  Control/orchestration/evidence plane
OpenTofu              =  IaC execution engine
```

## IaC Engine Interface

All IaC engines implement:

| Method | Purpose |
|---|---|
| `probe()` | Detect engine version/availability |
| `fmt()` | Format configuration |
| `init()` | Initialize provider plugins |
| `validate()` | Validate configuration syntax |
| `plan()` | Generate and save execution plan |
| `show()` | Machine-readable plan output |
| `apply()` | Apply a saved plan |
| `output()` | Get resource outputs |
| `destroy()` | Destroy resources |
| `state_reference()` | Path to IaC state file |

## Supported Engines

| Engine | Status |
|---|---|
| OpenTofu | IMPLEMENTED (v1.12.5) |
| Terraform | FUTURE |

## Isolation

Every run uses an isolated working directory under `.ai/infra-runs/<RUN-ID>/iac/`.
No shared state between unrelated runs.

## Safety

- No real AWS endpoints — all routed to fakecloud
- `NO_COLOR=1` for clean machine-readable output
- AWS credentials stripped from environment
- Subprocess argument arrays only (no `shell=True`)
- Command allowlist: `version fmt init validate plan show apply output`
