# INFRA-AGAIN Safety Model (AIRLOCK)

## Action Policy

| Policy | Meaning | Examples |
|---|---|---|
| AUTO | Execute without approval | Read, plan, PLAN_ONLY, validated local lab |
| ASK | Require user approval | Create resources, apply to sandbox, install deps |
| BLOCK | Blocked by default | Production mutation, sudo, secret exfiltration, hidden fallback |

## Safety by Execution Mode

| Mode | Create | Apply | Destroy | Modify |
|---|---|---|---|---|
| PLAN_ONLY | AUTO | AUTO (no-op) | AUTO (no-op) | AUTO (no-op) |
| SIMULATED | AUTO | AUTO | AUTO | AUTO |
| LOCAL_RUNTIME | AUTO | AUTO | AUTO | AUTO |
| SANDBOX | ASK | ASK | BLOCK | ASK |
| CONTROLLED_REAL | ASK | ASK | BLOCK | ASK |
| PRODUCTION | BLOCK | BLOCK | BLOCK | BLOCK |

## Blocked by Default

- sudo without explicit approval
- Unrestricted cloud admin
- Secret exfiltration
- Destructive operations outside managed scope
- Production mutation without explicit approval
- Hidden provider fallback

## Production Safety

Production must NEVER be an implicit continuation from local testing.
Each step up the ladder requires new explicit approval.
