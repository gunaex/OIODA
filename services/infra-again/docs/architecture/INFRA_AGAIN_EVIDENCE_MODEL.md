# INFRA-AGAIN Evidence Model

## Evidence Record

Every execution produces an Evidence record containing:
- Request snapshot
- Normalized intent
- Provider catalog version
- Architecture plan
- Policy decisions
- Approval records
- IaC plan output
- Execution logs
- Exit codes
- Observed resources (post-execution)
- Validation results
- Limitations
- Provider/platform metadata
- Execution target and fidelity
- Timestamps
- Correlation ID

## Evidence Types (Canonical)

| Type | Description |
|---|---|
| ARCHITECTURE_PLAN | Plan document with rationale |
| PLAN_APPROVAL | Approval decision and approver |
| IAC_OUTPUT | OpenTofu/Terraform plan/apply output |
| VALIDATION_RESULTS | Post-execution validation |

## Principles

1. **Not self-summary**: Evidence is external output, not executor self-description
2. **By-reference**: Large artifacts referenced, not embedded
3. **Immutable**: Evidence is append-only after execution
4. **Correlated**: All evidence linked by correlationId
5. **Fidelity-preserving**: Execution mode recorded with evidence

## Observe-After-Apply

```
Desired State
    ↓
Execute
    ↓
Observe Actual State
    ↓
Compare (drift detection)
    ↓
Validate
```

InfrastructureResult uses actual observed evidence where available.
This supports future drift detection, repair, and reconciliation.
