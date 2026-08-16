# VersusControl Reference Analysis

**Date:** 2026-08-09
**Analyst:** INFRA-AGAIN Phase 0/1

## Reference Repositories

| Repository | URL | Commit/Branch | License |
|---|---|---|---|
| ai-infrastructure-agent | https://github.com/VersusControl/ai-infrastructure-agent | 9725ca7 (main) | MIT |
| devops-ai-guidelines | https://github.com/VersusControl/devops-ai-guidelines | main | MIT |

## ai-infrastructure-agent Analysis

### Architecture Observations
- Go-based AI infrastructure agent
- Strong AWS coupling — agent is built around AWS service knowledge
- Uses MCP (Model Context Protocol) for tool integration
- Dry-run / approval model present
- State/conflict concepts modeled

### Useful Concepts
- Request → Discovery → Plan → Approval → Execution → Monitor pipeline
- Dry-run behavior as safety mechanism
- Approval gate before real execution
- MCP/tool approach for provider interaction

### Rejected Concepts
- **AWS-centric core**: The agent is tightly coupled to AWS. INFRA-AGAIN must remain provider-neutral.
- **LLM as cloud catalog**: The agent relies on LLM knowledge for AWS services. INFRA-AGAIN uses Dynamic Capability Registry.
- **Go language choice**: We chose Python for readability and ecosystem alignment with AGAIN.

### Adaptation Decision
- Adopt the pipeline pattern (request → plan → approve → execute → monitor)
- Reject AWS coupling — maintain strict provider neutrality
- Adopt approval gate concept but implement as AIRLOCK policy engine
- Reference the MCP pattern for future tool integration consideration

## devops-ai-guidelines Analysis

### Architecture Observations
- Comprehensive guidelines for AI in DevOps
- Tool registry concept
- Data classification framework
- Validation and output verification emphasis
- Access control and audit patterns
- Human review requirements

### Useful Concepts
- **Tool registry**: Model capabilities as registered tools
- **Data classification**: Sensitivity levels for infrastructure data
- **Validation**: Output verification before acceptance
- **Access control**: Granular permissions for AI agents
- **Audit trail**: Complete traceability
- **Human review**: Explicit approval gates for sensitive operations

### Rejected Concepts
- None significant — these are guidelines, not architecture

### Adaptation Decision
- Tool registry → Dynamic Capability Registry
- Data classification → AIRLOCK policy levels
- Validation → Observe-after-apply pattern
- Access control → AUTO/ASK/BLOCK policy engine
- Audit trail → Evidence model
- Human review → Approval gate in execution pipeline

## Key Takeaways for INFRA-AGAIN

1. **Pipeline pattern is well-established**: Plan → Approve → Execute → Validate
2. **Approval gates are essential**: Never auto-execute production changes
3. **Evidence is non-negotiable**: Every decision must be traceable
4. **Provider neutrality is our differentiator**: Reference impls are AWS-coupled; we are not
5. **MCP is worth watching**: May be useful for future provider tool integration
