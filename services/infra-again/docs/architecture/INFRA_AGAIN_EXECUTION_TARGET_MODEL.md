# INFRA-AGAIN Execution Target Model

## Target Abstraction

```
ExecutionTarget
├── mode          # PLAN_ONLY, SIMULATED, ..., PRODUCTION
├── provider      # AWS, GCP, ON_PREM, PRIVATE_CLOUD
├── platform      # NATIVE_VM, KUBERNETES, OPENSHIFT_OCP
├── targetType    # FAKECLOUD, KIND, CRC_OPENSHIFT, ...
├── endpoint      # Connection endpoint (optional)
├── capabilities  # Supported capabilities
├── fidelityNotes # Truthful fidelity documentation
├── safetyLevel   # 0 (PLAN_ONLY) to 6 (PRODUCTION)
└── provenance    # Source/target provenance
```

## Safety Ladder

| Level | Mode | Blast Radius | Default Policy |
|---|---|---|---|
| 0 | PLAN_ONLY | Zero | AUTO |
| 1 | SIMULATED | Zero | AUTO |
| 2 | LOCAL_RUNTIME | Local machine | AUTO |
| 3 | LOCAL_PRIVATE_CLOUD | Local machine | AUTO |
| 4 | SANDBOX | Sandbox account | ASK |
| 5 | CONTROLLED_REAL | Non-prod environment | ASK |
| 6 | PRODUCTION | Production | BLOCK |

## Fidelity Evidence

Every execution must preserve fidelity:
```
Example: fakecloud
  AWS API Compatibility       SIMULATED
  Real AWS Provisioning       NOT_TESTED
  Production Readiness        NOT_VERIFIED
```

Never convert emulator success into production-readiness claims.
