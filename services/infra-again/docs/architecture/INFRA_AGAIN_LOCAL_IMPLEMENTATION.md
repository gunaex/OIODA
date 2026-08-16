# INFRA-AGAIN — Local Implementation Architecture

## What INFRA-AGAIN Is

INFRA-AGAIN is a **provider-neutral infrastructure control plane** that governs the full lifecycle from architecture design through production readiness — with safety invariants enforced at every stage.

It separates **planning** from **execution**, **observation** from **validation**, and **verification** from **promotion** — ensuring no single actor or observation can unilaterally claim success.

## Control-Plane Architecture

```
Requirement → Architecture Design → Provider Intelligence → Infra Pulse
→ User Review → Design Acceptance → BASELINE_FROZEN

→ Implementation Planning → Plan Approval → Execution Readiness

→ AIRLOCK → Executor → Observer → Validator
→ Independent Verifier → Evidence → Cleanup/Reconciliation

→ Promotion → Rollback/Recovery Readiness → UAT
→ Separation of Duties → Production Readiness

→ LOCAL IMPLEMENTATION FREEZE
```

### Invariant: Planner ≠ Executor ≠ Observer ≠ Validator ≠ Verifier

```
EXECUTOR_SUCCESS != VERIFIED_SUCCESS
VERIFIED_SUCCESS != PROMOTION_APPROVED
PROMOTION_APPROVED != PRODUCTION_READY
PRODUCTION_READY != PRODUCTION_EXECUTION
```

Observation of actual state always wins over executor claims. Unknown state must never become PASS.

## Provider vs Platform

| Providers | Platforms |
|---|---|
| AWS | NATIVE_VM |
| GCP | KUBERNETES |
| ON_PREM | OPENSHIFT_OCP |
| PRIVATE_CLOUD | BARE_METAL |

**OCP is a platform, not a provider.** Provider and platform are independent dimensions.

Provider intelligence states (dynamic): DISCOVERED → METADATA_COLLECTED → CAPABILITY_MAPPED → SCHEMA_VALIDATED → EXECUTION_SUPPORT_CHECKED → VERIFIED → SUPPORTED.

Invariant: DISCOVERED != SUPPORTED, SUPPORTED != SAFE_TO_EXECUTE.

## Fidelity Levels

| Level | Policy | Description |
|---|---|---|
| PLAN_ONLY | AUTO | HCL/document generation only |
| SIMULATED | AUTO | Dry-run, no real resources |
| LOCAL_RUNTIME | AUTO (isolated) | Local execution with harness |
| LOCAL_PRIVATE_CLOUD | ASK | Local private cloud with harness |
| SANDBOX | ASK | Real cloud, isolated sandbox |
| CONTROLLED_REAL | BLOCK | Real cloud, controlled conditions |
| PRODUCTION | BLOCK | Real production |

No local environment may be labelled Production-equivalent unless actually proven.

## Safety Ladder

```
PLAN_ONLY          AUTO
SIMULATED          AUTO
LOCAL_RUNTIME      AUTO (isolated/run-owned)
LOCAL_PRIVATE_CLOUD ASK (generally)
SANDBOX            ASK
CONTROLLED_REAL    BLOCK
PRODUCTION         BLOCK
```

## Promotion Flow

Only allowed transitions: SANDBOX → CONTROLLED_REAL, CONTROLLED_REAL → PRODUCTION.

Blocked: SANDBOX → PRODUCTION, CONTROLLED_REAL → SANDBOX, PRODUCTION → anything, same → same.

Promotion packages persist across restarts with canonical SHA256 digests binding all security-critical fields. Approval requires:
- Digest verification (no mutation since creation)
- Authoritative plan/package rebind from persistence
- Source verification binding (Execution→Observation→Validation→Verification→Evidence)
- Separation of duties (requester ≠ approver)

## Rollback / Recovery

Rollback is a first-class control-plane flow. Rollback executor success is NOT recovery success.

States: DRAFT → READY → APPROVED → EXECUTED → VERIFIED/FAILED. Recovery reconciliation classifies: DESIRED_STATE_RESTORED, PARTIAL_STATE, UNKNOWN_STATE, RECOVERY_FAILED. UNKNOWN_STATE never equals SUCCESS.

## UAT / Separation of Duties

Production eligibility requires: UAT == PASSED, executor ≠ verifier, promotionRequester ≠ promotionApprover, uatPerformer ≠ productionPromotionApprover (where supported). Missing identity evidence → IDENTITY_EVIDENCE_INCOMPLETE (never assumes PASS).

UAT is immutable after PASS — any mutation of scope, criteria, evidence, environment, plan, or package invalidates UAT.

## Production Readiness

Authoritative decision evaluating ALL gates: PLAN_CURRENT, PACKAGE_CURRENT, PLAN_ID_MATCH, CHECKSUM_MATCH, SOURCE_EXECUTION_VERIFIED, SOURCE_EVIDENCE_VALID, PROMOTION_APPROVED, PROMOTION_NOT_EXPIRED, BLAST_RADIUS_VALID, ROLLBACK_APPROVED, MAINTENANCE_WINDOW_OPEN, UAT_PASSED, SEPARATION_OF_DUTIES_VALID, COST_WITHIN_LIMIT, RESOURCE_ALLOWLIST_VALID, OWNERSHIP_SCOPE_VALID.

Even READY returns `PRODUCTION_EXECUTION_ALLOWED=false, PRODUCTION=BLOCK` — this phase proves eligibility only.

## Real-Cloud Execution Boundary

Real cloud execution has **NOT** been performed. CONTROLLED_REAL and PRODUCTION are **BLOCKED** in policy. The admin safety belt (Argon2id password hashing, ImmutableApproval with SHA256 digests, GuardedAwsS3Mutator with AIRLOCK assertion) is implemented and verified at source level but has never been tested against real AWS.

## Admin Safety Belt

- `AdminAuth`: Argon2id/PBKDF2 password verification, max 3 attempts, storage at `~/.config/infra-again/admin-auth.json` (0600)
- `ImmutableApproval`: SHA256 canonical digest, seal/verify/save/load, mutation detection
- `AirlockContext`: State machine (DISCOVERY → AIRLOCK_PASSED → EXECUTING)
- `GuardedAwsS3Mutator`: Every S3 mutation asserts airlock first
- No legacy env flag can authorize real cloud; noninteractive real mutation defaults to BLOCK
- No plaintext credentials in code or configs

## Known Deferred Validations

- **REAL AWS validation is DEFERRED.** No AWS credentials are configured. No real S3 operations have been performed.
- Real GCP, ON_PREM, and PRIVATE_CLOUD validation are DEFERRED.
- Multi-approver quorum (N-of-M) is not yet implemented — current model is single approver.
- Automated rollback execution is not yet implemented — rollback plans are defined and approved but not auto-triggered.
- Integration with external UAT test suites is not yet implemented.
- Real cloud execution has NOT been performed. Implementation completeness does NOT imply real-cloud certification.

## Future Real-Cloud Phases (NOT IMPLEMENTED)

```
RC-1 — Real Cloud Read-Only Discovery
RC-2 — Real Sandbox Controlled Mutation
RC-3 — Real Sandbox Observe/Validate/Verify/Cleanup
RC-4 — Controlled Real Validation
RC-5 — Production Certification
```

These are OPTIONAL VALIDATION EXTENSIONS after local implementation freeze. AWS may be a first provider but must NOT be hard-coded as the definition of Real Cloud.

## Implementation Status

```
Phase 0-8: ACCEPTED / LOCAL_VERIFIED
Phase 9.1: REAL-CLOUD SAFETY CONTROLS IMPLEMENTED
Phase 9.2-9.5: PROMOTION/ROLLBACK/UAT/PRODUCTION_READINESS IMPLEMENTED
Phase 10: LOCAL IMPLEMENTATION FROZEN

REAL_AWS_SANDBOX=NOT_EXECUTED
AWS_MUTATION_API_CALLS=0
CONTROLLED_REAL=BLOCK
PRODUCTION=BLOCK
REAL_CLOUD_VALIDATION=DEFERRED
```
