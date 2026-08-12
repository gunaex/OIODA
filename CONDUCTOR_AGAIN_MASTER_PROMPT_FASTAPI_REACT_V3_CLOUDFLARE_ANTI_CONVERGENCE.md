# Conductor Again — Build Master Prompt
## FastAPI + React, matching the Again Platform family

**Document status:** Architecture and delivery baseline — Revision 0.3  
**Revision focus:** Cloudflare service layer + anti-convergence multi-agent governance  
**Target product:** Conductor Again  
**Target domain:** `conductoragain.kanphong.com`  
**Target repository:** `https://github.com/gunaex/Conductor_Again`  
**Primary sibling applications:** PM Again and QA Again  
**Core identity:** Project Control Plane + Skill and AI Capability Distributor

---

## Revision 0.3 — Cloudflare Service Layer and Anti-Convergence Governance

Revision 0.3 preserves every Revision 0.2 principle and adds two mandatory
architecture layers.

### A. Cloudflare service layer

```text
Cloudflare Pages
  React/Vite frontend hosting.

Cloudflare R2
  Private object and artifact storage.

Cloudflare Workers AI
  An additional external AI Resource in the unified pool.

Cloudflare Turnstile
  Bot and abuse challenge for selected authentication and high-risk flows.

Cloudflare Web Analytics
  Privacy-aware frontend performance analytics with sensitive-route controls.
```

FastAPI remains the core backend on Fly.io. SQLite remains the transactional
metadata and workflow store on the Fly.io persistent volume. R2 does not replace
the database, and Workers AI does not replace Conductor's own routing policy.

### B. Anti-convergence multi-agent governance

Multiple providers do not automatically guarantee independent thinking.
Long-running interaction can cause conformity, sycophancy, majority attraction,
authority bias, error propagation, and diversity collapse.

Conductor Again must therefore optimize for:

```text
Independent First Judgment
→ Preserved Disagreement
→ Evidence-based Review
→ Calibrated Confidence
→ Anonymous Critique
→ Explicit Revision Cause
→ Independent Decision
```

Consensus is an allowed outcome, not the objective.

A multi-agent workflow must never erase an initially correct minority merely
because later agents repeat the majority. Initial answers, revisions, dissent,
evidence, confidence, and decision provenance must remain independently
auditable.

### Revision 0.2 principle retained

> Register every approved AI account, API account, official subscription-backed
> tool, local runtime, and installed local model in one governed AI Resource Pool.
> Normal users do not choose a provider, account, or model for each task.
> Conductor Again resolves the Skill, evaluates every eligible resource, selects
> the Primary resource, prepares a Fallback Chain, executes the work, validates
> the result, and records why each resource was selected or rejected.

Unsupported or non-automatable subscription accounts remain visible with an
honest access mode such as `MANUAL_HANDOFF_ONLY`; they must never be
impersonated as an API.

---

## 0. Why this document exists

The Again Platform currently has two primary applications:

1. **PM Again** — project management and delivery planning.
2. **QA Again** — quality engineering, hybrid testing, evidence, defects, reports, and test governance.

The platform now needs a top-level product named **Conductor Again**.

Conductor Again is not another project-management screen, another QA application, or a chatbot placed on top of existing software. It is the project-level control plane that:

- receives and preserves Business Vision;
- identifies missing or ambiguous information;
- builds and governs Requirement Baselines;
- coordinates work across PM Again, QA Again, development tools, and future Again Apps;
- preserves traceability from Vision to Delivery and Quality Evidence;
- manages decisions, approvals, dependencies, risks, and cross-application impact;
- distributes governed **Skills** to applications, agents, workflows, and users;
- registers approved AI API accounts, official subscription-backed tools, and local models in one AI Resource Pool;
- automatically selects the best eligible resource for each Skill and prepares governed fallbacks;
- forms deliberately diverse AI panels for high-impact or uncertain work;
- prevents premature consensus through independent first-pass, blind review, dissent preservation, and anti-conformity controls;
- routes AI work through approved providers, accounts, models, tools, APIs, and local runtimes;
- stores large artifacts and immutable Skill packages in private Cloudflare R2;
- records exactly why a resource was selected or rejected and which human, rule, skill, model, application, or machine produced each result.

This document is the master build prompt. It defines the architecture, domain boundaries, delivery phases, constraints, and quality gates.

Do not start implementation from assumptions in this document alone. Before writing code, inspect the real sibling repositories and treat their working code as the ground truth for conventions.

---

## 1. Mandatory repository grounding before any code

### 1.0 Clone and preserve the Conductor Again repository

The target repository already exists:

```bash
git clone https://github.com/gunaex/Conductor_Again.git
cd Conductor_Again
```

This repository is the only target repository for the new product.

Before creating files:

- inspect the current branch, files, history, and working tree;
- preserve any existing work;
- do not initialize a second repository;
- do not copy PM Again or QA Again wholesale into this repository;
- reuse patterns deliberately and record deviations;
- keep small, reviewable commits and an annotated tag for every accepted phase.

If the repository is empty, create the agreed scaffold inside it only after
Phase 0 decisions are accepted.

### 1.1 Clone and read PM Again

```bash
git clone https://github.com/gunaex/PM-Again.git
```

At minimum, inspect the real equivalents of:

```text
backend/app/auth.py
backend/app/database.py
backend/app/main.py
backend/app/models.py
backend/app/activity.py
backend/app/excel_utils.py
backend/app/routers/
backend/.env.example
backend/Dockerfile
backend/fly.toml

frontend/src/App.jsx
frontend/src/components/Layout.jsx
frontend/src/auth/AuthContext.jsx
frontend/src/api/client.js
frontend/src/components/StatusBadge.jsx
frontend/vite.config.js
frontend/package.json
frontend deployment configuration
```

Confirm back:

- authentication and refresh-token behavior;
- master DB and per-project SQLite provisioning;
- route and dependency conventions;
- role enforcement;
- audit/activity logging;
- Excel import/export conventions;
- React route tree;
- application shell and design conventions;
- deployment and environment configuration.

### 1.2 Read QA Again

Read the actual QA Again repository available in the current workspace or supplied remote repository.

At minimum, inspect:

- immutable test-script revision design;
- test-cycle snapshot behavior;
- execution-result history;
- evidence storage and annotation;
- defect lifecycle;
- human and machine provenance;
- reporting formulas;
- export behavior;
- RBAC and audit implementation;
- UI conventions inherited from PM Again;
- any integration or external-project reference model.

If the QA Again repository URL is not supplied and the repository is not available in the workspace, stop before implementation and report this as a missing build dependency. Do not invent its conventions from memory.

### 1.3 Read the two source design documents

Use these documents as product intent:

```text
Conductor Again — Platform Vision and Architecture Design
QA-Again — Rebuild Master Prompt (FastAPI + React, matching PM-Again)
```

The repositories remain the implementation ground truth. The documents define intent and constraints.

### 1.4 Phase 0 rule

**Do not write feature code until the repository audit and Architecture Decision Records are completed.**

---

## 2. Product definition

### 2.1 Product name

The product name is:

> **Conductor Again**

“Orchestrator” describes its architectural role. It is not the product name.

### 2.2 Core product identity

Conductor Again has two inseparable responsibilities:

```text
A. Project Control Plane
B. Skill and AI Capability Control Plane
```

It must govern both the project workflow and the capabilities used to perform that workflow.

### 2.3 Project Control Plane responsibilities

Conductor Again owns:

- Business Vision;
- business objectives and success criteria;
- project-level constraints and assumptions;
- clarification questions and answers;
- canonical Business Requirements and revisions;
- business rules;
- cross-application orchestration;
- cross-application traceability;
- project-level decisions and approval gates;
- dependency and impact analysis;
- integration command/event history;
- project-level risk intelligence;
- AI and Skill recommendations;
- provenance and decision history.

### 2.4 Skill and AI Capability Control Plane responsibilities

Conductor Again must:

- maintain a governed Skill Registry;
- publish versioned Skill Packages;
- assign Skills to target applications, agents, roles, projects, and workflow states;
- resolve Skill compatibility and dependencies;
- distribute Skill versions without silently changing installed behavior;
- specify which runtime executes each Skill;
- select or recommend an allowed AI provider/model based on policy;
- enforce data-classification restrictions;
- track cost, quota, latency, errors, and usage;
- collect Skill Execution Results and provenance;
- revoke, suspend, roll back, or supersede unsafe or defective Skill versions;
- preserve human approval where required.

Conductor Again is the **distributor and governor** of Skills. It does not have to execute every Skill itself.

---

## 3. What Conductor Again must not become

Conductor Again must not become:

- a duplicate of PM Again;
- a duplicate of QA Again;
- a general-purpose chatbot;
- a monolithic system that owns every application’s data;
- a mandatory proxy for every local action;
- an autonomous agent swarm without governance;
- a shared database joining all applications;
- a hidden browser-automation layer that impersonates ChatGPT, Gemini, or Claude;
- a credential scraper;
- an AI system that can overwrite human evidence or final decisions;
- a premature enterprise workflow platform;
- a visual workflow builder in the MVP;
- a replacement for GitHub, GitLab, CI/CD, IDEs, or coding agents.

---

## 4. Data ownership boundaries

### 4.1 Conductor Again owns

```text
Business Vision
Business Objective
Success Criterion
Constraint
Assumption
Stakeholder Context
Clarification Question
Clarification Answer
Canonical Requirement
Requirement Revision
Business Rule
Decision
Approval Gate
Cross-App Dependency
Impact Analysis
Orchestration Case
Workflow State
Skill Definition
Skill Version
Skill Assignment
Skill Policy
AI Provider Configuration Metadata
Model Capability Metadata
Routing Policy
Artifact Reference
Trace Link
Command Record
Event Record
Provenance Record
Cross-App Risk
```

### 4.2 PM Again owns

```text
Project delivery plan
Epic
Feature
Task
Assignment
Timeline
Milestone
Sprint
Resource
Budget
Delivery progress
PM operational risk
PM activity history
```

Conductor stores references and selected read-model summaries, not duplicate PM records.

### 4.3 QA Again owns

```text
Test suite
Immutable script revision
Test case
Test cycle
Execution result
Execution history
Evidence
Annotation revision
Defect quality record
Test sign-off
QA report data
QA activity history
```

Conductor stores references, coverage summaries, readiness signals, and cross-project decisions. It does not duplicate test execution or evidence.

### 4.4 Source-code and deployment systems own

```text
Repository
Branch
Commit
Pull request
Code review
Build
Artifact
Deployment
Runtime health
```

Conductor stores references, statuses, correlation, decisions, and project impact.

### 4.5 No shared application database

PM Again, QA Again, and Conductor Again must have independent:

- repositories;
- deployments;
- databases;
- user sessions;
- secrets;
- operational ownership.

Integration must use explicit APIs, commands, events, and artifact references.

---

## 5. Skill architecture

### 5.1 Definition of a Skill

A **Skill** is a versioned, testable, governed capability package that tells an approved runtime how to perform a bounded task.

A Skill is not only a prompt.

A complete Skill may include:

```text
Manifest
Purpose and scope
Input schema
Output schema
System instructions
Prompt templates
Rule definitions
Tool permissions
Allowed target applications
Allowed execution runtimes
Model capability requirements
Provider restrictions
Data-classification policy
Budget and timeout policy
Human-approval policy
Fallback policy
Examples
Evaluation cases
Compatibility constraints
Dependency list
Version and release notes
Signature/checksum
Owner and approver
```

### 5.2 Example Skill categories

Initial Skill Packs may include:

```text
Vision Intake
Domain Discovery
Requirement Clarification
Requirement Completeness Review
Business Rule Extraction
Scope Decomposition
Workstream Planning
PM Work Breakdown
QA Test Design
Requirement-to-Test Coverage
Missing Requirement Detection
Defect Triage
Impact Analysis
Regression Planning
Release Readiness
Risk Summarization
Decision Brief
Project Status Brief
```

### 5.3 Skill package example

```yaml
apiVersion: again.platform/v1
kind: Skill
metadata:
  id: requirement-clarifier
  name: Requirement Clarifier
  version: 0.1.0
  owner: conductor-again
  status: published

spec:
  purpose: >
    Identify missing, ambiguous, conflicting, or unverifiable information
    in a project requirement and propose structured clarification questions.

  executionTargets:
    - CONDUCTOR_SERVER
    - TARGET_APP
    - LOCAL_AGENT

  inputSchemaRef: schemas/requirement-clarifier-input.json
  outputSchemaRef: schemas/requirement-clarifier-output.json

  capabilityRequirements:
    structuredOutput: true
    toolCalling: false
    minimumContextTokens: 16000
    reasoningLevel: medium

  modelPolicy:
    allowedProviderTypes:
      - OFFICIAL_API
      - LOCAL_MODEL
    preferredModelClass: balanced
    fallbackModelClass: economical
    maximumEstimatedCostUsd: 0.25

  dataPolicy:
    maximumClassification: INTERNAL
    externalProviderAllowed: true
    redactSecrets: true
    retainPrompt: false

  approvalPolicy:
    resultType: AI_RECOMMENDATION
    humanApprovalRequiredBefore:
      - REQUIREMENT_BASELINE_CHANGE

  dependencies: []
  evaluationSuite: evals/requirement-clarifier-v1.json
```

### 5.4 Skill lifecycle

```text
DRAFT
→ IN_REVIEW
→ APPROVED
→ PUBLISHED
→ DEPRECATED
→ RETIRED
```

Exceptional states:

```text
SUSPENDED
REVOKED
```

Rules:

- Published versions are immutable.
- Any change creates a new version.
- Projects may pin an exact Skill version.
- Deprecation does not silently upgrade pinned projects.
- Revocation blocks new execution and clearly flags affected projects.
- Rollback changes the active assignment, not historical execution records.
- Every Skill execution records the exact Skill version and checksum.

### 5.5 Skill distribution model

Conductor Again provides a **Skill Registry and Distribution API**.

Targets may:

- query available Skills;
- request installation;
- receive assigned Skills;
- pin a version;
- report compatibility;
- cache an approved package;
- report execution results;
- report evaluation failures;
- acknowledge revocation.

Distribution modes:

```text
PULL
Target application fetches an assigned Skill package.

PUSH_NOTIFICATION
Conductor notifies a target that an assignment changed; target then fetches it.

EMBEDDED_REFERENCE
A workflow references a Skill version and the selected runtime resolves it.

LOCAL_EXPORT
An approved Skill Pack is exported for a local agent or air-gapped environment.
```

Do not push executable code blindly into another application. Distribution must use signed/versioned artifacts, explicit compatibility checks, and target-side validation.

### 5.6 Skill execution planes

A Skill assignment must declare where it runs:

```text
CONDUCTOR_SERVER
For cross-application planning, routing, project intelligence, and decisions.

TARGET_APP
For domain-local work such as QA test design inside QA Again.

LOCAL_AGENT
For developer workstation, CLI, IDE, or on-premise execution.

EXTERNAL_TOOL
For an approved SaaS or provider-specific agent surface.

HUMAN_ASSISTED
For a generated recommendation completed or approved by a person.
```

This separation prevents Conductor from becoming a runtime bottleneck.

### 5.7 Skill assignment scope

A Skill may be assigned to:

```text
Platform
Application
Project
Role
User
Workflow type
Workflow state
Artifact type
Integration endpoint
```

Precedence must be deterministic and documented. Recommended precedence:

```text
Explicit Workflow Assignment
→ Project Assignment
→ Application Assignment
→ Platform Default
```

A more-specific assignment may restrict but must not silently bypass a platform security policy.

---

## 6. Unified AI Resource Pool and autonomous selection

### 6.1 Central operating principle

Conductor Again is the AI orchestrator.

All approved AI resources are registered once in a central:

> **AI Resource Pool**

Normal project workflows use:

```text
Selection Mode = AUTO
```

The user specifies the work, desired outcome, constraints, and data context.
The user should not normally have to select:

- OpenAI vs Gemini vs Claude;
- API Account 1 vs API Account 2;
- Codex Account 1 vs Codex Account 2;
- cloud model vs local model;
- small model vs large model;
- primary provider vs fallback provider.

Conductor Again must:

```text
Understand Work
→ Resolve Skill
→ Derive Capability Requirements
→ Apply Project and Data Policies
→ Inspect All Registered AI Resources
→ Reject Ineligible Resources
→ Score Eligible Resources
→ Select Primary Resource
→ Build Fallback and Escalation Chain
→ Acquire Execution Lease
→ Execute
→ Validate Output
→ Record Usage and Provenance
→ Update Observed Resource Performance
```

The selected provider/model/account remains visible and explainable, but it is
not a required choice in the normal user flow.

### 6.2 Register all resources, not only one preferred provider

The AI Resource Pool may contain any number of approved resources, including:

```text
OpenAI API — Company Account
OpenAI API — Personal Account
OpenAI API — Project-specific Account
Gemini API — Free Project
Gemini API — Paid Project
Vertex AI — Company Project
Anthropic API — Company Account
Anthropic API — Personal Account
Codex — Account 1
Codex — Account 2
Codex — Account 3
Claude Code — Account 1
Gemini CLI — Account 1
Local Runtime — OnexFly
Local Runtime — Desktop GPU
Local Runtime — Private Server
Local Model — Qwen
Local Model — Kimi
Local Model — Llama
Local Model — Coding Model
Manual ChatGPT Account
Manual Claude Account
Manual Gemini Account
```

Registration does not imply that every resource can be called in the same way.
Each resource must declare its real Access Mode and Entitlements.

### 6.3 Resource taxonomy

Do not collapse Account, Runtime, Model, and Entitlement into one record.

```text
AIProvider
The vendor or runtime family.

AIAccount
A provider account, API billing project, workspace, or subscription identity.

AIExecutionRuntime
The actual executable surface: official API, approved CLI/agent, local server,
desktop runtime, on-premise endpoint, or manual handoff.

InstalledModel
A model available through a runtime.

AIEntitlement
The operations the account/runtime is actually allowed to perform.

AIResource
A routable combination of account + runtime + model/profile + entitlement.

AIResourcePool
The governed set of all resources visible to the router.
```

One account may expose several resources. One local runtime may expose several
installed models. One model family may exist through several accounts.

### 6.4 Supported access modes

```text
OFFICIAL_API
Provider API key, service account, official OAuth, or provider-approved API
authorization that can be called by the Conductor backend.

OFFICIAL_SUBSCRIPTION_TOOL
A provider-approved subscription-backed CLI, coding agent, desktop tool, or
login flow, limited to the exact capabilities and automation scope officially
supported by that tool.

LOCAL_MODEL
A model running locally, on-premise, on a private GPU server, or through an
approved OpenAI-compatible local endpoint.

MANUAL_HANDOFF
Conductor prepares a governed Task Package for a person to execute in an
external AI product and imports the returned result with explicit
`HUMAN_SUBMITTED_EXTERNAL_AI_RESULT` provenance.

MOCK_OR_TEST
A deterministic or simulated runtime used for tests, contract validation, and
offline development. It must never be represented as a real AI execution.
```

### 6.5 Non-negotiable provider rule

Conductor Again must use legal, explicit, provider-approved access methods only.

Never:

- scrape a consumer chat website;
- store provider account passwords;
- reuse browser cookies or session tokens;
- automate an interactive subscription UI as though it were a server API;
- bypass provider quotas, limits, billing, or terms;
- rotate accounts for the purpose of evading an enforced limit;
- claim that a consumer subscription automatically includes general API usage;
- claim exact quota/reset data when no approved source exists.

A resource that cannot be automated legally remains in the pool as
`MANUAL_HANDOFF`, not as a fake API.

### 6.6 Subscription, API billing, and entitlement are distinct

The architecture must separately represent:

```text
Consumer or workspace subscription
API billing account or cloud project
API key/service credential
Official tool-specific subscription entitlement
Local-runtime entitlement
Manual chat access
```

Examples such as ChatGPT, Codex, Gemini, Gemini CLI, Claude, and Claude Code
must be represented through provider or tool adapters, but every adapter must
declare what it can actually do.

Example entitlements:

```text
SERVER_INFERENCE
STRUCTURED_OUTPUT
TOOL_CALLING
VISION_INPUT
DOCUMENT_INPUT
CODE_AGENT
CLI_EXECUTION
LOCAL_INFERENCE
MANUAL_CHAT
USAGE_QUERY
RESET_TIME_QUERY
FILE_ACCESS
REPOSITORY_ACCESS
```

The router must not select a resource for an operation outside its entitlement.

### 6.7 AI Resource model

Each routable resource should contain:

```text
Resource ID
Display name
Provider
Account reference
Execution runtime reference
Access mode
Model/profile reference
Entitlements
Capabilities
Allowed projects
Allowed users/roles
Allowed data classifications
Geographic or residency restriction
Health state
Quota state
Budget state
Concurrency limit
Current active leases
Priority
Cost class
Latency class
Quality class
Historical Skill evaluation scores
Historical production success rate
Last successful execution
Last error
Enabled/suspended/revoked state
```

Example:

```json
{
  "id": "air_openai_company_reasoning_01",
  "displayName": "OpenAI API — Company Reasoning",
  "provider": "OPENAI",
  "accountId": "aia_openai_company",
  "runtimeId": "rt_openai_official_api",
  "accessMode": "OFFICIAL_API",
  "modelProfileId": "mp_reasoning_large",
  "entitlements": [
    "SERVER_INFERENCE",
    "STRUCTURED_OUTPUT",
    "TOOL_CALLING"
  ],
  "capabilities": [
    "TEXT_GENERATION",
    "LONG_CONTEXT",
    "CODE_REASONING"
  ],
  "allowedDataClassifications": [
    "PUBLIC",
    "INTERNAL"
  ],
  "status": "AVAILABLE",
  "routing": {
    "basePriority": 50,
    "maximumConcurrency": 3
  }
}
```

### 6.8 Local resources

Local and private resources are first-class pool members, not emergency
fallbacks only.

Example topology:

```text
OnexFly Runtime
├─ Qwen general model
├─ Kimi reasoning model
├─ Coding model
└─ Embedding model

Desktop GPU Runtime
├─ Vision model
├─ Fast classifier
└─ Private document model

Private Server Runtime
├─ vLLM endpoint
└─ OpenAI-compatible endpoint
```

Each local runtime reports:

```text
online/offline state
endpoint health
installed models
loaded model
VRAM/RAM requirements
context limit
concurrency
queue depth
estimated local compute cost
last benchmark
last Skill evaluation
```

Restricted project data should prefer or require a local/private resource when
policy demands it.

### 6.9 Capability registry

Skills request normalized capabilities rather than provider marketing names.

```text
TEXT_GENERATION
STRUCTURED_OUTPUT
TOOL_CALLING
VISION
DOCUMENT_UNDERSTANDING
LONG_CONTEXT
CODE_REASONING
FAST_CLASSIFICATION
EMBEDDING
REPOSITORY_AGENT
BROWSER_AGENT
LOCAL_EXECUTION
PRIVATE_DEPLOYMENT
THAI_LANGUAGE
MULTILINGUAL
```

Each Model Profile records:

```text
provider model ID
display name
capabilities
context limit
input/output types
tool support
structured-output support
data-handling class
region availability
estimated pricing metadata
latency class
quality class
active/deprecated state
last verified timestamp
Skill evaluation results
```

Provider model lists, pricing, limits, and availability change. Treat them as
configuration or synchronized metadata with a verification timestamp, not
hard-coded permanent truth.

### 6.10 Health, budget, quota, and availability snapshots

Conductor should maintain time-stamped snapshots:

```text
HealthSnapshot
BudgetSnapshot
QuotaSnapshot
RateLimitSnapshot
SubscriptionResetSnapshot
LocalRuntimeSnapshot
ConcurrencySnapshot
```

Possible resource states:

```text
AVAILABLE
BUSY
DEGRADED
RATE_LIMITED
BUDGET_WARNING
BUDGET_EXHAUSTED
OFFLINE
AUTH_EXPIRED
POLICY_BLOCKED
MANUAL_ONLY
SUSPENDED
REVOKED
UNKNOWN
```

Unknown is not the same as available.

When exact subscription usage or reset information is unavailable, store:

```text
value = null
source = MANUAL or UNAVAILABLE
confidence = UNKNOWN
```

Do not fabricate a number.

### 6.11 Autonomous eligibility filtering

Before scoring, reject every resource that fails a hard condition:

```text
resource disabled, suspended, or revoked
runtime offline
authentication invalid
missing entitlement
missing required capability
context limit too small
input type unsupported
project not allowed
role/user not allowed
data classification prohibited
region/residency prohibited
hard budget exhausted
hard quota exhausted
concurrency unavailable
Skill compatibility failed
Skill evaluation below hard threshold
provider prohibited by project policy
```

Every rejection must be recorded as a Routing Candidate Decision.

### 6.12 Autonomous scoring

Eligible resources receive an explainable score.

Default weighted dimensions may include:

```text
Capability and Skill Fit          25%
Privacy and Data Policy Fit       20%
Skill Evaluation Quality          15%
Current Availability              10%
Historical Success                10%
Estimated Cost                     7%
Expected Latency                   5%
Remaining Budget/Quota             5%
Project or Account Preference      3%
```

Weights are policy configuration, not constants hidden in code.

Example score record:

```json
{
  "resourceId": "air_local_onexfly_qwen",
  "eligible": true,
  "totalScore": 84.2,
  "components": {
    "capabilityFit": 100,
    "privacyFit": 100,
    "evaluationQuality": 82,
    "availability": 90,
    "historicalSuccess": 85,
    "cost": 95,
    "latency": 65,
    "remainingCapacity": 70,
    "preference": 50
  },
  "warnings": [
    "Latency is above the project target"
  ]
}
```

### 6.13 Primary, fallback, and escalation chain

Every automatic decision should produce:

```text
Primary Resource
Fallback 1
Fallback 2
Optional Escalation Resource
Manual Handoff Route
```

Fallback may occur when:

- provider returns retryable error;
- rate limit is reached;
- runtime goes offline;
- execution lease expires;
- output fails schema validation;
- output confidence is below policy;
- Skill evaluation guard rejects the response;
- cost estimate changes beyond approval threshold.

Do not fallback to a resource that violates data policy merely because the
primary failed.

Escalation differs from fallback:

```text
Fallback
Another resource expected to perform the same quality class of work.

Escalation
A stronger or more expensive resource intentionally selected because the task
proved more complex or the lower-cost result failed a quality threshold.
```

### 6.14 Selection modes

The default is:

```text
AUTO
```

Admin/project policy may expose:

```text
AUTO
AUTO_PREFER_LOCAL
AUTO_PRIVATE_ONLY
AUTO_LOWEST_COST
AUTO_HIGHEST_QUALITY
AUTO_FASTEST
PIN_RESOURCE
MANUAL_HANDOFF_ONLY
```

`PIN_RESOURCE` is an exception for testing, regulated work, debugging, or an
explicit project decision. Normal users should not be forced to choose.

A selection mode is still subordinate to hard security and data policies.

### 6.15 Multiple accounts and fair account allocation

Multiple accounts from the same provider are valid pool members.

Conductor may allocate across them based on:

```text
project ownership
company vs personal boundary
remaining approved budget
current concurrency
known quota
known reset time
health
historical success
data policy
cost center
explicit account reservation
```

The purpose is reliable and governed workload allocation, not quota evasion.

Required controls:

- account ownership and cost-center labels;
- project allow-list;
- maximum concurrency;
- daily/monthly budget;
- fair-use policy;
- cooldown after rate limiting;
- no automatic retry loop across accounts without a bounded limit;
- audit trail of every account selection.

### 6.16 Execution leases and concurrency

Before an automatic execution begins, Conductor should acquire an
`ExecutionLease`.

The lease prevents:

- selecting the same limited account beyond concurrency;
- duplicate execution after retry;
- local GPU overcommit;
- two workers running the same orchestration step;
- unbounded fallback storms.

Lease fields:

```text
lease ID
resource ID
request ID
workflow ID
acquired at
expires at
heartbeat
concurrency slot
release reason
```

### 6.17 Provider and tool adapters

Design interfaces for:

```text
OpenAI Official API Adapter
Google Gemini API Adapter
Google Vertex AI Adapter
Cloudflare Workers AI Adapter
Anthropic Official API Adapter
Official Codex Tool Connector
Official Claude Code Connector
Official Gemini CLI Connector
OpenAI-Compatible Local Adapter
Ollama Adapter
vLLM Adapter
LM Studio Adapter
Manual Handoff Adapter
Mock/Test Adapter
```

The registry may hold every account before every executable connector is
implemented. Connector status must be honest:

```text
SUPPORTED
PARTIALLY_SUPPORTED
MANUAL_ONLY
PLANNED
DISABLED
```

Do not delay the whole platform until every provider adapter is complete.
Implement adapters incrementally while preserving the unified pool contract.

### 6.18 AI request envelope

```json
{
  "requestId": "airq_01H...",
  "projectId": "prj_01H...",
  "workflowId": "wf_01H...",
  "selectionMode": "AUTO",
  "skill": {
    "id": "requirement-clarifier",
    "version": "0.2.0",
    "checksum": "sha256:..."
  },
  "dataClassification": "INTERNAL",
  "capabilityRequirements": {
    "structuredOutput": true,
    "minimumContextTokens": 16000,
    "reasoningLevel": "medium",
    "languages": ["th", "en"]
  },
  "routingPolicyId": "route_default_internal_v2",
  "budget": {
    "maximumEstimatedCostUsd": 0.25
  },
  "inputArtifactRefs": [
    {
      "ownerSystem": "CONDUCTOR_AGAIN",
      "artifactType": "REQUIREMENT_REVISION",
      "externalId": "REQ-12@3"
    }
  ]
}
```

The request does not require `provider`, `account`, or `model` in AUTO mode.

### 6.19 Routing decision and execution result

Store the routing decision separately from the execution result.

```json
{
  "routingDecisionId": "rtd_01H...",
  "requestId": "airq_01H...",
  "selectionMode": "AUTO",
  "selectedPrimaryResourceId": "air_local_onexfly_qwen",
  "fallbackResourceIds": [
    "air_gemini_paid_balanced",
    "air_openai_company_reasoning"
  ],
  "escalationResourceId": "air_anthropic_company_large",
  "candidateCount": 12,
  "eligibleCount": 4,
  "decisionPolicyVersion": "route_default_internal_v2",
  "reason": [
    "Data classification allows local execution",
    "Primary passed the Skill evaluation threshold",
    "Primary has the best combined privacy/cost/quality score"
  ]
}
```

Execution result:

```json
{
  "requestId": "airq_01H...",
  "routingDecisionId": "rtd_01H...",
  "status": "SUCCEEDED",
  "resourceId": "air_local_onexfly_qwen",
  "provider": "LOCAL",
  "accessMode": "LOCAL_MODEL",
  "modelId": "installed-model-id",
  "skillId": "requirement-clarifier",
  "skillVersion": "0.2.0",
  "inputTokens": null,
  "outputTokens": null,
  "estimatedCostUsd": 0.0,
  "latencyMs": 1830,
  "confidence": 0.82,
  "resultType": "AI_RECOMMENDATION",
  "warnings": [
    "Runtime did not report token counts"
  ],
  "provenanceId": "prov_01H..."
}
```

Do not fake usage values. Use `null` plus a warning when the resource cannot
report them.

### 6.20 Routing explainability

For every request, the UI and audit API must answer:

```text
What Skill was requested?
What capabilities were required?
Which resources were considered?
Which resources were rejected and why?
How were eligible resources scored?
Which resource was selected?
What fallback chain was prepared?
Did fallback or escalation occur?
What did the execution cost?
What quota/budget state was observed?
What human or policy approval applied?
```

Example timeline:

```text
Requirement Clarifier requested
↓
Local Qwen eligible — score 84.2 — selected Primary
↓
Gemini Paid eligible — score 78.5 — selected Fallback 1
↓
OpenAI Company eligible — score 77.1 — selected Fallback 2
↓
Claude Manual Account rejected — MANUAL_HANDOFF only
↓
Execution succeeded on Local Qwen
```

### 6.21 Resource administration UI

Provide an administrative **AI Resources** area:

```text
Overview
Accounts
Execution Runtimes
Installed Models
Entitlements
Capabilities
Health
Quota and Reset
Budgets
Concurrency
Skill Evaluation
Routing Decisions
Usage History
Secrets and Rotation
```

Example list:

```text
Resource                         Access Mode                 Status
OpenAI Company API               OFFICIAL_API               AVAILABLE
Gemini Free Project              OFFICIAL_API               RATE_LIMITED
Claude Company API               OFFICIAL_API               AVAILABLE
Codex Account 1                  OFFICIAL_SUBSCRIPTION_TOOL  BUSY
Codex Account 2                  OFFICIAL_SUBSCRIPTION_TOOL  AVAILABLE
OnexFly Qwen                     LOCAL_MODEL                AVAILABLE
Desktop Kimi                     LOCAL_MODEL                OFFLINE
ChatGPT Personal                 MANUAL_HANDOFF             MANUAL_ONLY
```

Normal project pages should show `Automatic` and the selected result, not a
mandatory provider dropdown.

### 6.22 Secrets and credential storage

Provider credentials:

- must never be returned to the frontend after creation;
- must never be written to normal logs;
- must not be stored as plaintext in SQLite;
- should use deployment secrets for platform-managed credentials;
- may use envelope/application encryption for BYOK credentials;
- require rotation, revocation, ownership, and last-used metadata;
- must be separated from non-secret account metadata;
- must support disabling one account without deleting execution history.

### 6.23 Performance feedback without uncontrolled self-modification

Conductor may update observed metrics such as:

```text
success rate
schema-valid rate
average latency
average cost
Skill evaluation score
human acceptance rate
retry rate
```

These observations may influence routing within approved policy bounds.

Conductor must not autonomously rewrite hard security policy, data policy,
provider allowance, Skill definitions, or routing weights without an explicit
versioned policy change and human approval.

---


## 7. Multi-Agent Deliberation and Anti-Convergence Governance

### 7.1 Risk statement

Using several AI providers is not sufficient by itself.

Agents may still:

- anchor on the first visible answer;
- follow a numerical majority;
- defer to a model perceived as stronger;
- repeat an authoritative tone without verifying evidence;
- adopt peer errors near their own competence boundary;
- gradually align after repeated interaction;
- produce a confident but incorrect cascade;
- lose semantic and strategic diversity over long-running collaboration;
- preserve provider diversity while collapsing to the same reasoning pattern.

The system must treat **conformity and diversity collapse as observable failure
modes**, not merely prompting problems.

### 7.2 Research-informed design basis

The design is informed by published findings showing that:

- LLM agents exhibit measurable conformity and may align with a majority or a
  more capable-seeming peer;
- agents that are accurate in isolation can become vulnerable under social
  influence;
- dense communication can accelerate premature convergence;
- initially correct answers may be lost during consensus-seeking debate;
- response anonymization can reduce identity-driven sycophancy and self-bias;
- diversity of initial viewpoints and calibrated confidence are important;
- consensus-free or trajectory-aware decisions can outperform last-round
  majority voting in some settings.

Relevant research includes:

```text
Conformity, Confabulation, and Impersonation:
Persona Inconstancy in Multi-Agent LLM Collaboration — 2024

Do as We Do, Not as You Think:
The Conformity of Large Language Models — 2025

An Empirical Study of Group Conformity in Multi-Agent Systems — 2025

Conformity and Social Impact on AI Agents — 2026

Conformity Dynamics in LLM Multi-Agent Systems:
The Roles of Topology and Self-Social Weighting — 2026

Free-MAD: Consensus-Free Multi-Agent Debate — ACL Findings 2026

Diversity Collapse in Multi-Agent LLM Systems:
Structural Coupling and Collective Failure in Open-Ended Idea Generation
— ACL Findings 2026

Demystifying Multi-Agent Debate:
The Role of Confidence and Diversity — ACL Findings 2026

When Identity Skews Debate:
Anonymization for Bias-Reduced Multi-Agent Reasoning — ACL 2026
```

These references guide the architecture but do not replace project-specific
evaluation. Every protocol must be benchmarked using Conductor's own Skills and
real project tasks.

### 7.3 Safety objective

The goal is not to force disagreement forever.

The goal is to ensure that:

```text
Agreement happens because evidence and reasoning support it,
not because agents observed that other agents already agreed.
```

Conductor must preserve:

- independence before interaction;
- diversity of candidate hypotheses;
- traceability of opinion changes;
- minority evidence;
- uncertainty;
- alternative options;
- human visibility into unresolved disagreement.

### 7.4 Deliberation is policy-triggered, not used for every request

Multi-agent deliberation consumes time, quota, and money.

Use a single eligible resource for routine bounded work unless policy triggers a
panel.

Possible triggers:

```text
HIGH_IMPACT decision
LOW_CONFIDENCE result
CONFLICTING_REQUIREMENTS
CROSS_DOMAIN analysis
SECURITY or PRIVACY concern
RELEASE or QUALITY gate
ARCHITECTURE decision
SIGNIFICANT_SCOPE_CHANGE
CRITICAL_DEFECT
PROVIDER disagreement
HUMAN_REQUESTED_REVIEW
RANDOM_AUDIT_SAMPLE
```

The trigger and chosen protocol must be recorded.

### 7.5 Independent first pass is mandatory

For every deliberation panel:

1. Build one canonical Source Packet.
2. Freeze the Source Packet version.
3. Send it independently to every selected panel member.
4. Do not expose peer answers, provider names, model names, ranks, or confidence
   during the first pass.
5. Store every first-pass answer as an immutable `IndependentSubmission`.
6. Wait until all required submissions complete or time out.
7. Only then begin comparison or critique.

Sequential prompting where Agent B sees Agent A before producing an independent
answer is prohibited for governed deliberation.

### 7.6 Source Packet rules

The first-pass Source Packet contains:

```text
Task definition
Skill ID and version
Decision criteria
Input artifact references
Approved project facts
Known assumptions
Known constraints
Required output schema
Allowed tools and retrieval scope
Data classification
Budget and deadline
```

It must not contain:

```text
Previous panel consensus
Unlabeled AI-generated summary presented as fact
Provider identity hierarchy
A preferred answer
A manager's desired conclusion unless it is an explicit constraint
Hidden ranking of agents
```

For long-running projects, do not give a new panel only the previous consensus
summary. Include source artifacts, the Assumption Ledger, and unresolved
Dissent Records so a fresh panel can re-evaluate the actual evidence.

### 7.7 Diverse panel construction

Panel selection is different from normal fallback routing.

The objective is not merely to choose the top three resources by the same score.

A panel should maximize meaningful diversity across:

```text
Provider
Model family
Training/alignment lineage where known
Local vs external execution
Model size/class
Tool and retrieval strategy
Assigned analytical role
Prompt framing
Historical error correlation
Historical Skill disagreement
Evidence-source behavior
```

Provider diversity alone is not enough. Different providers may still share
similar training data, safety tuning, benchmarks, or dominant assumptions.

The panel builder must apply concentration limits such as:

```text
Maximum members from one provider
Maximum members from one model family
Maximum members using the same retrieval result set
Minimum number of independent evidence paths
Minimum role diversity
```

Exact values are versioned policy.

### 7.8 Panel roles

Use explicit, rotated roles.

Possible roles:

```text
PROPOSER
ALTERNATIVE_PROPOSER
DOMAIN_ANALYST
ASSUMPTION_CHALLENGER
EVIDENCE_CHECKER
RISK_ANALYST
RED_TEAM
IMPLEMENTATION_REVIEWER
QUALITY_REVIEWER
PRIVACY_REVIEWER
COST_REVIEWER
INDEPENDENT_JUDGE
JURY_MEMBER
```

Rules:

- no permanent “smartest agent” or permanent chair;
- roles rotate across deliberations;
- role assignment is recorded but hidden from peers when unnecessary;
- a critic must identify valid strengths as well as weaknesses;
- a proposer must state uncertainty and alternatives;
- a Red Team is not instructed to disagree blindly—it must challenge using
  evidence, counterexamples, failure modes, or missing assumptions.

### 7.9 Structured answer contract

Do not request or persist private hidden chain-of-thought.

Every agent returns a concise, reviewable structure:

```text
Conclusion
Recommended action
Key claims
Evidence references
Assumptions
Uncertainties
Known limitations
Counterarguments considered
Failure conditions
Confidence
Evidence quality
What would change this conclusion
```

`Confidence` and `Evidence quality` are separate fields.

Confidence without supporting evidence must not dominate the group.

### 7.10 Confidence calibration

Self-reported confidence is only one signal.

Conductor should maintain empirical calibration by:

```text
Skill
Resource
Model profile
Domain
Decision type
```

Possible observations:

```text
Historical correctness
Human acceptance rate
Schema-valid rate
Defect escape rate
False-positive rate
Calibration error
Performance near competence boundary
```

The deliberation protocol may reveal anonymized confidence after an initial
content-first review, but provider/model identity remains hidden from peer
agents.

Recommended sequence:

```text
Stage A — evaluate content and evidence blindly
Stage B — reveal calibrated confidence
Stage C — allow evidence-based revision
```

### 7.11 Blind and anonymized peer review

Before peer review:

- remove provider name;
- remove account name;
- remove model name;
- remove resource rank;
- remove statements such as “the strongest model said”;
- randomize answer order;
- use neutral labels such as Candidate A, Candidate B, Candidate C.

Anonymization mapping is retained only in protected provenance.

### 7.12 Sparse, staged communication topology

Do not default to all-to-all free conversation.

Dense communication can increase cost and accelerate convergence.

Preferred MVP topology:

```text
Round 0 — independent private submissions
Round 1 — anonymized cross-critique
Round 2 — private revision with explicit change reasons
Round 3 — independent judge or jury evaluation
```

Default maximum:

```text
One independent round
One critique round
One revision round
One decision round
```

Additional rounds require policy or human approval.

### 7.13 Revision protocol

A revised answer must preserve the original and state:

```text
Previous conclusion
New conclusion
Changed or unchanged
New evidence received
Specific critique accepted
Specific critique rejected
Assumption changed
Confidence before
Confidence after
Reason for change
```

Invalid change reason:

```text
“I agree with the others.”
```

Valid change reason:

```text
“Candidate B supplied requirement REQ-17 and test evidence EV-42, which
contradict my assumption that published BOM revisions remain editable.”
```

If the conclusion changes without new evidence, corrected fact, exposed
assumption, or valid logical critique, flag it as a potential conformity event.

### 7.14 Preserve dissent and minority reports

Every materially different position must remain accessible.

Create a `DissentRecord` when:

- a panel member rejects the leading recommendation;
- a minority identifies a unique risk;
- evidence conflicts;
- confidence remains materially split;
- a reviewer believes the decision criteria are incomplete;
- consensus was reached only after unsupported opinion changes.

A Dissent Record contains:

```text
Position
Supporting evidence
Rejected majority assumptions
Risk if minority is correct
Suggested verification
Owner
Status
Resolution or acceptance
```

The final decision may proceed while keeping accepted residual risk visible.

### 7.15 Consensus is not the target

Allowed outcomes:

```text
SUPPORTED_AGREEMENT
SUPPORTED_MAJORITY_WITH_DISSENT
UNRESOLVED_DISAGREEMENT
INSUFFICIENT_EVIDENCE
HUMAN_DECISION_REQUIRED
ADDITIONAL_EXPERIMENT_REQUIRED
POLICY_BLOCKED
```

Do not force every panel to return one answer.

### 7.16 Decision aggregation

Do not use simple last-round majority voting as the sole decision rule.

Preferred decision signals:

```text
Evidence relevance
Evidence independence
Requirement traceability
Factual consistency
Policy compliance
Skill evaluation score
Calibrated historical reliability
Counterexample survival
Risk severity
Implementation feasibility
Minority evidence
```

A judge must score criteria explicitly.

The final decision is a new artifact, not a rewritten copy of the majority
answer.

### 7.17 Independent judge and jury

The final judge should preferably:

- not participate as a proposer;
- receive anonymized candidate submissions;
- see original and revised positions;
- see evidence and dissent;
- evaluate against a fixed rubric;
- not see provider/account identity before scoring;
- declare conflicts or insufficient evidence;
- produce a structured Decision Recommendation.

For high-impact decisions, use either:

```text
One fresh independent judge + human approval
```

or:

```text
Small independent jury + human approval
```

The judge must not be the same execution instance that generated the leading
proposal unless no alternative exists and the exception is recorded.

### 7.18 Anti-convergence metrics

Track at least:

```text
Initial Conclusion Diversity
Initial Semantic Diversity
Provider Concentration
Model-Family Concentration
Role Diversity
Evidence Source Diversity
Evidence Overlap Ratio
Disagreement Rate
Opinion Change Rate
Majority Attraction Rate
Unsupported Agreement Rate
Minority Survival Rate
Confidence Synchronization
Convergence Velocity
Same-Model Correlation
Cross-Provider Correlation
Judge Independence
Human Override Rate
Post-Decision Defect Rate
```

Metrics must be interpreted by task type. High agreement is expected for simple
deterministic questions and suspicious only when unsupported or inconsistent
with evidence.

### 7.19 Conformity and diversity-collapse alerts

Create `ConformityAlert` or `DiversityCollapseAlert` when configurable rules
detect patterns such as:

- two or more agents change toward the majority without new evidence;
- semantic diversity drops sharply immediately after peer exposure;
- all agents converge on identical wording or assumptions after one round;
- minority evidence disappears from the final decision;
- confidence rises collectively without improved evidence;
- a high-status resource disproportionately changes peers;
- the same provider/model family dominates panel membership;
- an initially correct candidate is discarded without refutation;
- repeated project decisions reuse the same provider mix and same assumptions;
- long-running agents no longer generate alternatives.

Alerts do not automatically mean the result is wrong. They require review or a
recovery action.

### 7.20 Recovery actions

Possible policy actions:

```text
FREEZE_CURRENT_DECISION
REQUEST_HUMAN_REVIEW
SPAWN_FRESH_INDEPENDENT_PANEL
ADD_DIFFERENT_PROVIDER
ADD_LOCAL_MODEL
ADD_DOMAIN_SPECIALIST
ADD_RED_TEAM
RESET_CONTEXT_FROM_SOURCE_ARTIFACTS
REQUEST_NEW_EVIDENCE
RUN_DETERMINISTIC_CHECK
RUN_TEST_OR_EXPERIMENT
USE_CONSENSUS_FREE_SCORING
PRESERVE_MINORITY_AS_BLOCKING_RISK
```

A fresh panel must not see the previous majority conclusion before producing its
own independent submissions.

### 7.21 Long-running anti-drift controls

For workflows lasting days, weeks, or months:

- periodically create a fresh-context review;
- rotate providers and roles;
- retain an Assumption Ledger;
- retain an unresolved Dissent Ledger;
- compare current conclusions with the original Requirement Baseline;
- sample completed decisions for independent re-audit;
- prevent one rolling chat transcript from becoming the only project memory;
- summarize from source artifacts, not only from prior AI summaries;
- expire stale confidence and health observations;
- detect repeated phrase/claim inheritance across agents;
- require new evidence before closing old dissent.

### 7.22 Memory isolation

Separate:

```text
Project Facts
Human Decisions
Verified Machine Results
AI Recommendations
Agent Working Memory
Deliberation Transcripts
Dissent Records
```

A consensus summary is not promoted to Project Fact automatically.

Only an approved decision, verified evidence, or authoritative source may
change canonical project state.

### 7.23 Data model

```text
DeliberationPolicy
DeliberationCase
PanelDefinition
PanelMember
RoleAssignment
SourcePacket
IndependentSubmission
Claim
EvidenceReference
AssumptionDeclaration
ConfidenceDeclaration
BlindCandidate
PeerCritique
OpinionRevision
DissentRecord
MinorityReport
DiversitySnapshot
ConformitySignal
ConformityAlert
DecisionRubric
JudgeAssignment
JudgeScore
JuryVote
DecisionRecommendation
DeliberationOutcome
RecoveryAction
```

### 7.24 Deliberation state

```text
DRAFT
→ SOURCE_PACKET_FROZEN
→ PANEL_SELECTED
→ INDEPENDENT_ROUND
→ INDEPENDENT_ROUND_COMPLETE
→ BLIND_REVIEW
→ PRIVATE_REVISION
→ DIVERSITY_CHECK
→ JUDGING
→ WAITING_FOR_HUMAN
→ DECIDED
```

Alternative states:

```text
INSUFFICIENT_DIVERSITY
CONFORMITY_ALERT
ADDITIONAL_EVIDENCE_REQUIRED
FRESH_PANEL_REQUIRED
POLICY_BLOCKED
CANCELLED
```

### 7.25 User interface

The decision view must show:

```text
Task and decision criteria
Source Packet version
Panel composition summary without unnecessary identity bias
Independent first-pass positions
Evidence map
Critiques
Opinion changes and reasons
Confidence before/after
Diversity metrics
Conformity alerts
Minority reports
Judge rubric
Final human/system decision
```

Do not present a polished consensus paragraph while hiding disagreement.

### 7.26 MVP anti-convergence protocol

For high-impact BOM decisions, use a minimum panel such as:

```text
Member A — business/domain analysis
Member B — quality and edge-case analysis
Member C — implementation/risk analysis
Fresh Judge — decision rubric
Human — approval
```

Requirements:

- at least two distinct provider/model families when policy allows;
- first-pass isolation;
- anonymized critique;
- one private revision;
- preserved minority report;
- independent judge;
- human approval;
- full provenance.

### 7.27 Example: Circular BOM rule

Question:

```text
Should the system prevent only direct self-reference,
or every transitive circular dependency?
```

Independent first pass might produce:

```text
Candidate A
Prevent direct and transitive cycles at save time.

Candidate B
Allow draft cycles but block publish/activation.

Candidate C
Reject all cycles immediately and also scan imported BOMs.
```

The system must not collapse these into “all agree that cycles are bad.”

It must preserve the actual design choices:

- validation timing;
- draft behavior;
- import behavior;
- performance implications;
- existing data remediation;
- audit requirements.

The final decision must cite the chosen business rule and explain why rejected
alternatives were not selected.

### 7.28 Testing requirements

Test:

- independent submissions cannot see peer outputs;
- peer identities are anonymized;
- answer order is randomized;
- original submissions remain immutable;
- revisions require structured change reasons;
- unsupported majority-following raises a signal;
- dissent remains visible after decision;
- a fresh judge has not participated as proposer;
- a fresh panel does not receive the previous conclusion;
- provider/model concentration policy is enforced;
- deterministic questions do not trigger false diversity alarms excessively;
- human approval is required where policy specifies;
- retries do not leak peer answers into the independent round.

---

## 8. Human, Rule, Skill, AI, Machine, and System provenance

Every meaningful result must identify its origin.

Actor types:

```text
HUMAN
RULE_ENGINE
SKILL
AI_MODEL
MACHINE_ASSERTION
APPLICATION
SYSTEM_WORKFLOW
EXTERNAL_SYSTEM
```

Every provenance record should contain:

```text
actor type
actor identity
timestamp
source application
project
workflow
Skill ID/version/checksum
provider and model where applicable
access mode
input artifact references
output artifact references
rule or model version
confidence or warning
execution context
correlation ID
causation ID
decision history
```

The UI must visually distinguish:

```text
Rule Result
AI Recommendation
Machine Assertion
Human Decision
System Decision
Imported External Result
```

AI must never:

- convert a human FAIL to PASS;
- claim execution happened without evidence;
- invent a test result;
- approve a critical requirement automatically;
- hide uncertainty;
- overwrite an immutable published artifact;
- silently change a Skill version;
- silently switch to a provider prohibited by project policy.

---

## 9. Technical foundation

Match the sibling-family conventions after repository inspection.

### 9.1 Backend

Recommended baseline:

```text
Python 3.11
FastAPI
SQLAlchemy declarative models
Pydantic
SQLite
bcrypt
PyJWT
slowapi
python-dotenv
httpx
pytest
ruff
```

Use the actual PM Again dependency versions where practical.

### 9.2 Database pattern

Follow PM Again and QA Again unless Phase 0 discovers a hard blocker:

```text
master.db
data/projects/{slug}.db
```

Master DB may contain:

```text
users
refresh_tokens
project_registry
integration_registry
provider_account_metadata
platform_skill_catalog
platform_policies
global_reference_data
```

Per-project DB may contain:

```text
vision
vision_revisions
objectives
success_criteria
constraints
assumptions
stakeholders
clarification_questions
clarification_answers
requirements
requirement_revisions
business_rules
decisions
approval_gates
dependencies
risks
impact_analyses
orchestration_cases
workflow_steps
artifact_references
trace_links
skill_assignments
ai_requests
ai_results
command_records
event_records
provenance_records
activity_log
```

Use additive schema patches if that is the established sibling convention. Published revision content must remain immutable.


### 9.3 Cloudflare R2 object and artifact storage

Use a storage abstraction with Cloudflare R2 as the production MVP backend.

R2 stores unstructured or large objects. It does not replace SQLite.

Store in R2:

```text
Published Skill packages
Skill evaluation fixtures
Uploaded source documents
Context Packages
Manual Handoff packages
AI-generated artifacts
Large export files
Audit export bundles
Encrypted SQLite backup snapshots
Optional evidence or attachment objects introduced later
```

Keep in SQLite:

```text
Object metadata
Ownership
Project association
Artifact type
Object key
Checksum
Size
MIME type
Storage status
Retention policy
Version
Access policy
Created by
Created at
Deleted/expired state
Trace links
```

Required production characteristics:

- private buckets only;
- separate development and production buckets;
- no public `r2.dev` access for protected objects;
- S3-compatible API through a backend storage adapter;
- short-lived pre-signed upload/download URLs where appropriate;
- backend authorization before issuing a URL;
- opaque object keys, never trust a user filename as a path;
- content checksum;
- real MIME/signature validation where feasible;
- file-size and project-quota enforcement;
- immutable keys for published Skill packages;
- explicit retention and deletion state;
- audit event for upload, download authorization, replacement, and deletion;
- no secrets inside object metadata;
- CORS restricted to approved frontend origins.

Recommended object-key pattern:

```text
projects/{project_id}/
  skills/{skill_id}/{version}/{checksum}/package.zip
  source-documents/{artifact_id}/{revision}/{object_id}
  context-packages/{workflow_id}/{package_id}.zip
  ai-artifacts/{request_id}/{artifact_id}
  exports/{export_id}/{filename}
  backups/{backup_id}/{encrypted_snapshot}
```

Frontend upload flow:

```text
Frontend
→ request upload authorization from FastAPI
→ FastAPI validates project, role, type, size, and quota
→ FastAPI creates pending ObjectRecord
→ FastAPI returns short-lived pre-signed upload URL
→ Frontend uploads directly to R2
→ Frontend/backend completes upload
→ Backend verifies metadata/checksum and marks object AVAILABLE
```

Downloads follow the same authorization principle.

SQLite backup rules:

- use SQLite's online backup mechanism or a controlled consistent snapshot;
- do not copy an actively mutating DB file blindly;
- encrypt the snapshot before upload;
- store checksum and encryption-key reference;
- test restore;
- define retention and rotation;
- never make backup objects public.

The implementation must verify current Cloudflare pricing and limits during
Phase 0/1. As an initial planning assumption in August 2026, R2 Standard storage
includes a monthly free allocation, but free-tier values are operational
metadata, not permanent architecture constants.

### 9.4 SQLite deployment constraint

In the initial Fly.io architecture:

- use a persistent volume;
- run one write-capable backend instance;
- do not scale multiple writers over one local SQLite volume;
- document backup and restore;
- use transactional writes;
- use an outbox table for reliable integration publication;
- define the future threshold for moving to PostgreSQL.

### 9.5 Authentication

Follow PM Again’s proven pattern:

- short-lived JWT access token;
- httpOnly secure cookie;
- hashed opaque refresh token;
- refresh-token rotation;
- Bearer token support for direct API testing;
- role dependencies at router level;
- explicit CORS origins;
- secure production cookie flags;
- rate limiting;
- security headers;
- Cloudflare Turnstile verification for policy-selected abuse-sensitive flows.

Conductor Again authentication remains independent from PM Again and QA Again in the MVP.

### 9.6 Initial roles

Recommended:

```text
ADMIN
CONDUCTOR
APPROVER
CONTRIBUTOR
VIEWER
```

Possible service identity:

```text
SERVICE
```

Do not reuse human login tokens for service-to-service integration.

### 9.7 Frontend

Recommended baseline matching the Again family:

```text
React 19
Vite
Tailwind v4
react-router-dom
axios
vite-plugin-pwa
```

Use the actual sibling versions after inspection.

Requirements:

- project-list route outside the project shell;
- nested routes under `/:slug`;
- shared Layout pattern;
- role-aware navigation for UX;
- backend-enforced authorization;
- named API functions;
- consistent loading, empty, error, and permission states;
- PWA caching only static assets;
- no caching of live project or AI execution responses;
- Cloudflare Web Analytics only under the approved privacy policy;
- no sensitive project names, document names, secrets, or query values in analytics URLs/events.

### 9.8 Product-family design

Conductor Again must look related to PM Again and QA Again:

- same spacing language;
- same typography hierarchy;
- same button and modal conventions;
- same table behavior;
- same badge construction;
- same error/loading/empty states;
- distinct product accent allowed;
- no new design system unless an explicit family-wide decision is made.

Suggested identity:

```text
PM Again        Indigo
QA Again        Green
Conductor Again Amber or Purple
```

Treat the final accent as a product decision, not an architecture requirement.

---

## 10. Cloudflare service layer and deployment topology

### 10.1 Target topology

```text
kanphong.com
  Minimal independent landing page.
  Image only. No app links.

pmagain.kanphong.com
  PM Again frontend.

qaagain.kanphong.com
  QA Again frontend.

api.qaagain.kanphong.com
  QA Again backend.

conductoragain.kanphong.com
  Conductor Again frontend on Cloudflare Pages.

api.conductoragain.kanphong.com
  Conductor Again backend on Fly.io.
```

### 10.2 Service responsibility map

```text
Cloudflare DNS
  Domain and DNS management.

Cloudflare Pages
  Static React/Vite frontend.

Cloudflare R2
  Private object and artifact storage.

Cloudflare Workers AI
  Optional external AI execution resource in the AI Resource Pool.

Cloudflare Turnstile
  Bot/abuse challenge for selected flows.

Cloudflare Web Analytics
  Privacy-aware frontend performance analytics.

Fly.io
  FastAPI core backend and background worker.

Fly.io persistent volume
  SQLite transactional databases and temporary controlled processing space.
```

### 10.3 Core deployment boundary

```text
Frontend: Cloudflare Pages
Backend: Fly.io
Transactional metadata/workflow state: SQLite on Fly.io volume
Object/artifact storage: Cloudflare R2
```

Conductor Again is an independent deployment, not a route inside PM Again or
QA Again.

Do not move the core FastAPI backend to Cloudflare Workers, D1, or Pages
Functions merely because the frontend and object storage use Cloudflare.

### 10.4 Cloudflare Pages

Production environment baseline:

```text
VITE_API_BASE_URL=https://api.conductoragain.kanphong.com
```

Create:

```text
frontend/public/_redirects
```

with:

```text
/* /index.html 200
```

PWA rules:

- cache static build assets only;
- do not cache API results;
- do not cache AI decisions;
- do not cache project-sensitive documents;
- do not cache pre-signed object URLs longer than their validity.

### 10.5 Cloudflare R2

Recommended buckets:

```text
conductor-again-dev
conductor-again-prod
```

Optional backup separation:

```text
conductor-again-backups-prod
```

Required environment/secret configuration may include:

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_ENDPOINT
R2_PRESIGN_TTL_SECONDS
R2_MAX_UPLOAD_BYTES
```

Do not expose R2 credentials to the frontend.

R2 usage and free allocation are budget inputs. The implementation must read
current official limits rather than hard-code assumptions. At the time of this
revision, the published Standard-storage free allocation includes storage and
operation allowances and no internet egress charge, but those values may change.

### 10.6 Cloudflare Workers AI

Workers AI is registered as:

```text
Provider: CLOUDFLARE
Access Mode: OFFICIAL_API
Runtime: WORKERS_AI
Resource Pool: ENABLED
```

Suitable candidate Skills may include:

```text
Fast classification
Entity extraction
Tagging
Short summarization
Embedding where an approved model fits
Low-cost structured preprocessing
Independent panel member for selected tasks
```

Rules:

- Workers AI remains subject to project data policy;
- it is external processing, not equivalent to a local model;
- models and capabilities are discovered/configured, not permanently hard-coded;
- quota and reset observations feed the AI Resource Pool;
- a daily free allocation is a cost optimization, not a reliability guarantee;
- exceeding a free allocation must produce a clear quota state and fallback;
- do not select it merely because it is free if quality or privacy requirements
  are not satisfied.

Workers AI must pass the same Skill evaluations as every other resource.

### 10.7 Cloudflare Turnstile

Use Turnstile selectively for:

```text
Repeated failed login
Password reset
Invitation acceptance
Provider credential creation or replacement
High-risk administrator action
Suspicious automation or abuse signal
Public-facing form introduced later
```

Do not rely on frontend widget success alone.

Flow:

```text
Frontend obtains Turnstile token
→ sends token with protected request
→ FastAPI verifies token server-side with Cloudflare
→ FastAPI validates expected hostname/action and token freshness
→ protected action proceeds or is rejected
```

Turnstile complements, not replaces:

- authentication;
- rate limiting;
- lockout/cooldown;
- authorization;
- audit logging.

Use Cloudflare's official test keys in automated/local tests.

### 10.8 Cloudflare Web Analytics

Web Analytics may be enabled for performance and page-level usage, subject to
privacy review.

Rules:

- do not send document names, Requirement text, Skill inputs, AI outputs,
  provider secrets, or user-entered content;
- avoid sensitive project slugs in tracked URLs;
- prefer route templates or analytics limited to landing/login/non-sensitive
  shell pages;
- do not treat Web Analytics as the application's audit log;
- core operational telemetry remains in Conductor;
- document exactly where the analytics beacon is enabled.

### 10.9 Optional Cloudflare Access

Cloudflare Access may be evaluated as an outer gate for a private deployment.

It is optional and does not replace Conductor authentication.

If enabled:

- preserve app-level user identity and RBAC;
- define service-token access for PM Again and QA Again;
- ensure webhooks and service-to-service calls are not accidentally blocked;
- document emergency/break-glass access;
- record the decision in an ADR.

### 10.10 Cloudflare services not selected for the MVP

Do not add without an explicit ADR and demonstrated need:

```text
Cloudflare D1
Cloudflare KV
Durable Objects
Cloudflare Queues
Pages Functions for the core API
A second transactional database
A second workflow engine
```

Reasons:

- avoid duplicated state ownership;
- avoid two backend runtimes;
- avoid premature distributed architecture;
- preserve FastAPI/SQLite sibling conventions;
- keep debugging and backup behavior understandable.

### 10.11 Free-tier guardrails

Free tiers are capacity constraints, not product guarantees.

For each Cloudflare service, store or document:

```text
Current plan
Current published free allocation
Current usage
Warning threshold
Hard stop or paid-overage policy
Reset period
Last verified date
Source of truth
Fallback behavior
```

Warnings should occur before exhaustion.

A free-tier change must not silently break a critical workflow.

---

## 11. Integration architecture

### 11.1 MVP architectural pattern

Use:

```text
Modular Monolith
+ REST Commands
+ Transactional Outbox
+ Idempotent Event Inbox
+ Database-backed Workflow State Machine
+ Background Worker
```

Do not start with Kafka, Kubernetes, or distributed microservices.

### 11.2 Command and event distinction

A Command requests work:

```text
CreateDeliveryPlan
CreateQualityDesign
ProposeFixTask
RequestRetest
PublishSkillAssignment
RevokeSkillVersion
```

An Event reports a fact:

```text
DeliveryPlanCreated
QualityDesignCreated
DefectRaised
FixCompleted
RetestCompleted
SkillAssignmentPublished
SkillExecutionCompleted
SkillVersionRevoked
```

Do not use events as hidden commands.

### 11.3 Required integration envelope fields

```text
messageId
messageType
schemaVersion
correlationId
causationId
workflowId
projectId
originSystem
targetSystem
occurredAt
idempotencyKey
actor
artifactReferences
payload
```

### 11.4 Delivery behavior

Implement:

- idempotent handlers;
- retry with bounded exponential backoff;
- dead-letter or failed-message state;
- operator-visible retry;
- correlation timeline;
- timeout state;
- cancellation policy;
- partial-failure visibility;
- schema-version checks.

### 11.5 Do not create a bottleneck

Local application operations remain local.

Examples that do not require Conductor:

```text
Edit a PM task
Move a task between sprint states
Write a QA test step
Attach QA evidence
Execute a QA test
Edit a local draft
```

Conductor coordinates when work crosses boundaries:

```text
Requirement baseline approved
Requirement changed
Scope changed
Defect affects delivery
Test coverage is incomplete
Release decision required
Skill assignment changes
Provider policy blocks execution
Cross-app dependency changes
```

PM Again and QA Again must remain usable if Conductor is temporarily unavailable.

---

## 12. Core domain model

### 12.1 Project context

```text
Workspace
ProjectContext
Vision
VisionRevision
Objective
SuccessCriterion
Constraint
Assumption
Stakeholder
```

### 12.2 Requirement governance

```text
ClarificationQuestion
ClarificationAnswer
Requirement
RequirementRevision
BusinessRule
RequirementBaseline
BaselineApproval
```

### 12.3 Orchestration

```text
OrchestrationCase
WorkflowDefinition
WorkflowInstance
WorkflowStep
Transition
CommandRecord
EventRecord
RetryAttempt
```

### 12.4 Cross-app traceability

```text
ArtifactReference
TraceLink
Dependency
ImpactAnalysis
ImpactCandidate
CoverageSummary
```

Example Artifact Reference:

```json
{
  "id": "aref_01H...",
  "ownerSystem": "QA_AGAIN",
  "artifactType": "TEST_CASE",
  "externalId": "TC-BOM-0012",
  "externalVersion": "4",
  "projectExternalId": "bom-poc",
  "displayKey": "TC-BOM-0012",
  "url": "https://qaagain.kanphong.com/bom-poc/test-cases/TC-BOM-0012",
  "lastObservedAt": "2026-08-02T00:00:00Z"
}
```

### 12.5 Decisions and governance

```text
DecisionProposal
Recommendation
Decision
ApprovalGate
ApprovalAction
Policy
PolicyEvaluation
Risk
```

### 12.6 Skill control plane

```text
Skill
SkillVersion
SkillDependency
SkillCompatibility
SkillEvaluationSuite
SkillEvaluationRun
SkillAssignment
SkillDistribution
SkillInstallation
SkillRevocation
ExecutionTarget
```

### 12.7 AI Resource Pool and capability control plane

```text
AIResourcePool
AIProvider
AIAccount
AIEntitlement
AIExecutionRuntime
LocalRuntime
InstalledModel
ProviderAdapter
AgentConnector
CredentialReference
ModelProfile
Capability
HealthSnapshot
QuotaSnapshot
BudgetSnapshot
RateLimitSnapshot
SubscriptionResetSnapshot
ConcurrencySnapshot
RoutingPolicy
RoutingCandidate
RoutingScore
RoutingDecision
FallbackChain
ExecutionLease
AIRequest
AIExecution
UsageRecord
BudgetPolicy
QuotaState
FallbackAttempt
EscalationAttempt
```

### 12.8 Object and Cloudflare service control plane

```text
ObjectRecord
ObjectRevision
ObjectUploadSession
ObjectAccessGrant
ObjectChecksum
ObjectRetentionPolicy
StorageQuota
StorageUsageSnapshot
BackupSnapshot
BackupRestoreRun
CloudflareServiceProfile
CloudflareUsageSnapshot
TurnstileVerification
AnalyticsPrivacyPolicy
```

### 12.9 Multi-agent deliberation and anti-convergence

```text
DeliberationPolicy
DeliberationCase
PanelDefinition
PanelMember
RoleAssignment
SourcePacket
IndependentSubmission
Claim
EvidenceReference
AssumptionDeclaration
ConfidenceDeclaration
BlindCandidate
PeerCritique
OpinionRevision
DissentRecord
MinorityReport
DiversitySnapshot
ConformitySignal
ConformityAlert
DecisionRubric
JudgeAssignment
JudgeScore
JuryVote
DecisionRecommendation
DeliberationOutcome
RecoveryAction
```

### 12.10 Provenance and audit

```text
Actor
ProvenanceRecord
ActivityLog
DecisionHistory
ArtifactRevision
```

---

## 13. Workflow and state design

### 13.1 Generic orchestration state

```text
DRAFT
READY
WAITING_FOR_INPUT
WAITING_FOR_APPROVAL
QUEUED
IN_PROGRESS
PARTIALLY_COMPLETED
BLOCKED
FAILED_RETRYABLE
FAILED_FINAL
COMPLETED
CANCELLED
SUPERSEDED
```

Transitions must be explicit and validated.

### 13.2 Requirement lifecycle

```text
DRAFT
→ CLARIFYING
→ READY_FOR_REVIEW
→ APPROVED_BASELINE
→ CHANGE_PROPOSED
→ REAPPROVAL_REQUIRED
→ SUPERSEDED
```

### 13.3 Skill execution lifecycle

```text
CREATED
→ POLICY_CHECK
→ ROUTED
→ QUEUED
→ RUNNING
→ SUCCEEDED
```

Alternative outcomes:

```text
REJECTED_BY_POLICY
WAITING_FOR_APPROVAL
RATE_LIMITED
PROVIDER_UNAVAILABLE
FAILED_RETRYABLE
FAILED_FINAL
CANCELLED
MANUAL_HANDOFF_REQUIRED
```

### 13.4 Human approval gates

Human approval is required before:

- approving a Requirement Baseline;
- changing an approved Requirement;
- changing significant Scope, Budget, or Timeline;
- accepting a high or critical risk;
- overriding a quality gate;
- approving a production release;
- closing or accepting a critical defect;
- changing restricted-data provider policy;
- assigning a Skill with elevated tool permissions;
- publishing or revoking a platform-wide Skill;
- executing an AI request above configured budget;
- accepting an AI recommendation as a project decision.

---

## 14. Rule engine, small models, large models, and Skills

### 14.1 Deterministic Rule Engine

Use for:

- required fields;
- permission checks;
- state transitions;
- date overlap;
- duplicate active version;
- traceability completeness;
- approval policy;
- Skill compatibility;
- provider allowance;
- budget threshold;
- data-classification enforcement.

### 14.2 Small or local model

Use for bounded work such as:

- classification;
- entity extraction;
- defect summarization;
- similar-requirement detection;
- basic requirement-to-test mapping;
- risk tagging;
- simple completeness review;
- structured routing assistance.

### 14.3 Large model

Use only when needed:

- unfamiliar business domain;
- ambiguous requirement;
- conflicting business rules;
- cross-module impact;
- architecture proposal;
- test strategy;
- complex delivery sequencing;
- deep edge-case discovery;
- low-confidence escalation.

### 14.4 Skills define the work; models supply capabilities

Do not create one Skill per model.

Correct relationship:

```text
Skill
  declares required capabilities and policy

Routing Engine
  selects an allowed provider/model/runtime

Execution
  records the exact provider/model used
```

This allows the same Skill to run through OpenAI, Gemini, Claude, or a local model without changing its business identity, provided the selected model passes compatibility and evaluation.

---

## 15. MVP scope

### 15.1 MVP product slice

The MVP must prove both orchestration and independent deliberation.

For routine work, AUTO may select one resource.

For high-impact decisions in the golden flow, policy must invoke a diverse
multi-agent panel with independent first-pass, preserved dissent, and a fresh
judge.

The MVP must prove:

```text
Vision
→ Clarification
→ Approved Requirement Baseline
→ Skill-governed analysis
→ PM Again delivery reference
→ QA Again quality reference
→ Traceability
→ Defect
→ Impact analysis
→ Fix proposal
→ Retest
→ Closure decision
```

### 15.2 Golden business use case

Use a bounded Production BOM slice:

```text
Create Versioned BOM
Approve BOM
Activate BOM
Prevent Circular BOM
Raise Defect
Analyze Impact
Create Fix Proposal
Retest
Close
```

Do not build an ERP.

Exclude from the first vertical slice unless required by the selected flow:

```text
MRP
Purchasing
Inventory accounting
Full cost roll-up
Multi-site
Multi-company
Advanced routing
Production scheduling
Data migration platform
```

### 15.3 Initial Skill Pack for the MVP

Build only the Skills required for the golden flow:

```text
SKILL-001 Vision Intake
SKILL-002 BOM Domain Clarifier
SKILL-003 Requirement Completeness Review
SKILL-004 Scope Decomposer
SKILL-005 PM Delivery Plan Proposal
SKILL-006 QA Test Design Proposal
SKILL-007 Defect Triage
SKILL-008 Impact Analysis
SKILL-009 Regression Scope Proposal
SKILL-010 Decision Brief
SKILL-011 Independent Critique
SKILL-012 Evidence Review
SKILL-013 Minority Risk Report
SKILL-014 Decision Judge
```

Each Skill requires:

- immutable version;
- schemas;
- example inputs and outputs;
- policy;
- evaluation cases;
- provenance;
- human-review behavior.

### 15.4 Initial AI Resource Pool support

The registry and administration model must support adding **all approved
accounts and local resources** from the first usable MVP.

A registered resource may have connector status:

```text
SUPPORTED
PARTIALLY_SUPPORTED
MANUAL_ONLY
PLANNED
DISABLED
```

Minimum executable routes for the first usable MVP:

```text
1 official external API resource
1 Cloudflare Workers AI resource
1 local-model resource
1 mock/test resource
1 manual-handoff resource
```

Minimum governed deliberation capability:

```text
At least 3 independently executed panel submissions
At least 2 provider/model families when policy permits
1 anonymized critique round
1 private revision round
1 fresh judge
1 preserved Dissent Record
```

Also register every known OpenAI/ChatGPT/Codex, Gemini, Claude/Claude Code,
company API, personal API, and local-runtime account with its truthful Access
Mode and Entitlements, even when its executable connector is planned for a
later phase.

Normal workflow selection must default to:

```text
AUTO
```

The router must consider all currently eligible registered resources and
produce a Primary, Fallback Chain, and explainable Routing Decision.

Do not delay the MVP until every provider connector is implemented. The pool
contract supports all resources; connectors become executable incrementally.

---

## 16. End-to-end golden flow

1. User creates a Conductor project.
2. User enters: “Build a Production BOM system for a food factory.”
3. Conductor stores Vision Revision 1.
4. `Vision Intake` Skill extracts objectives, constraints, and assumptions.
5. Routing policy selects an approved provider or local model.
6. Result is stored as `AI_RECOMMENDATION`, not a requirement.
7. `BOM Domain Clarifier` Skill proposes questions about:
   - versioning;
   - approval;
   - effective dates;
   - circular references;
   - yield;
   - editing after activation.
8. Human answers the questions.
9. `Requirement Completeness Review` Skill identifies remaining gaps.
10. Human approves Requirement Baseline 1.
11. Conductor sends a delivery-planning command to PM Again.
12. PM Again owns and creates Project/Epic/Feature records.
13. PM Again returns Artifact References.
14. Conductor sends a quality-design command to QA Again.
15. QA Again owns and creates Test Scenarios/Test Cases.
16. QA Again returns Artifact References and coverage.
17. Conductor builds trace links:
    ```text
    Vision → Requirement → PM Feature → QA Test Case
    ```
18. QA executes the circular-BOM case.
19. QA records FAIL with evidence and raises a defect.
20. QA emits or returns `DefectRaised`.
21. Conductor opens an Impact Analysis orchestration case.
22. `Defect Triage` and `Impact Analysis` Skills propose:
    - affected requirement;
    - affected PM feature;
    - impacted tests;
    - timeline risk;
    - regression candidates.
23. Human/PM confirms priority and fix proposal.
24. Development occurs through the existing source-code workflow.
25. Fix completion is reported.
26. Conductor requests QA retest.
27. QA owns and records the retest result and evidence.
28. Conductor prepares a Decision Brief.
29. Human closes the orchestration case.
30. The complete decision and provenance history remains auditable.

---

## 17. Suggested delivery phases

Use small, reviewable commits and an annotated tag per accepted phase.

### Phase 0 — Repository audit and ADRs

Deliver:

- PM Again convention report;
- QA Again convention report;
- architecture gap analysis;
- domain ownership matrix;
- ADR set;
- integration-contract draft;
- threat-model draft;
- final MVP boundary.

Required ADRs:

```text
ADR-001 Data Ownership
ADR-002 Independent vs Shared Authentication
ADR-003 REST Command and Event Pattern
ADR-004 Workflow State Machine
ADR-005 Skill Package Format
ADR-006 Skill Distribution and Execution Planes
ADR-007 AI Provider and Tool Access Modes
ADR-008 Unified AI Resource Pool Model
ADR-009 AI Entitlements and Connector Truthfulness
ADR-010 Credential Storage and BYOK
ADR-011 Automatic Routing, Scoring, and Explainability
ADR-012 Account Allocation, Quota, Budget, and Concurrency
ADR-013 Requirement Ownership
ADR-014 Dev Again as Integration Layer
ADR-015 SQLite Constraints and PostgreSQL Exit Criteria
ADR-016 Cloudflare R2 Object and Backup Storage
ADR-017 Cloudflare Workers AI Resource Adapter
ADR-018 Turnstile Abuse Protection
ADR-019 Web Analytics Privacy Boundary
ADR-020 Multi-Agent Deliberation Protocol
ADR-021 Anti-Convergence Metrics and Alert Policy
ADR-022 Independent Judge and Dissent Preservation
ADR-023 Cloudflare Access Optional Outer Gate
```

Gate:

```text
No feature code.
All architecture decisions documented.
MVP scope approved.
```

### Phase 1 — Foundation and production-shaped deployment

Deliver:

- backend scaffold;
- frontend scaffold;
- auth;
- project registry;
- health check;
- activity log;
- Cloudflare Pages preview;
- Fly.io backend;
- persistent volume;
- private Cloudflare R2 development bucket;
- storage adapter and signed-upload smoke test;
- encrypted SQLite backup to R2 and restore smoke test;
- Cloudflare Turnstile test-mode server verification;
- Web Analytics privacy decision and safe enablement scope;
- CORS/cookie verification;
- custom-domain documentation;
- Cloudflare free-tier/budget guardrail document.

Gate:

```bash
cd backend && ruff check . && pytest
cd frontend && npm run lint && npm run build
```

Also verify:

```text
Real frontend-to-backend login in a deployed preview
Private R2 upload/download authorization
Backup restore from R2
Turnstile server-side verification
No sensitive values emitted to Web Analytics
```

### Phase 2 — Vision and requirement foundation

Deliver:

- Project Context;
- Vision and immutable revisions;
- objectives;
- constraints;
- assumptions;
- stakeholders;
- clarification questions/answers;
- requirement draft;
- requirement revision;
- baseline approval;
- provenance.

Gate:

```text
Vision → Clarification → Approved Baseline works manually without AI.
```

### Phase 3 — Skill Registry and Distribution MVP

Deliver:

- Skill catalog;
- Skill versions;
- immutable published package stored in private R2;
- checksum and storage metadata;
- manifest validation;
- assignment;
- project pinning;
- compatibility checks;
- evaluation cases;
- export/fetch API;
- revoke/deprecate behavior;
- Skill provenance.

Gate:

```text
A target runtime can fetch an assigned exact Skill version,
validate it, execute a mock, and return a traceable result.
```

### Phase 4 — Unified AI Resource Pool and Automatic Router

Deliver:

- AI Resource Pool;
- account registry;
- runtime registry;
- installed local-model registry;
- Entitlement model;
- connector-status model;
- provider/tool-adapter interface;
- one official API adapter;
- Cloudflare Workers AI adapter;
- one local-model adapter;
- mock/test adapter;
- manual-handoff adapter;
- registration of all known approved accounts and local resources;
- encrypted BYOK or platform-secret strategy;
- capability registry;
- health/quota/budget/concurrency snapshots;
- Selection Mode `AUTO`;
- hard eligibility filters;
- configurable scoring;
- Primary/Fallback/Escalation decision;
- Execution Lease;
- bounded retry and fallback;
- routing explainability;
- usage records;
- result provenance.

Gate:

```text
The same Skill is submitted without naming a provider, account, or model.
Conductor evaluates the whole registered pool, rejects ineligible resources,
selects a Primary, prepares a Fallback Chain, executes through at least one
official API and one local route, and stores a complete explainable decision.
```


### Phase 5 — Independent Deliberation and Anti-Convergence MVP

Deliver:

- Deliberation Policy;
- policy triggers;
- diverse panel builder;
- provider/model concentration constraints;
- frozen Source Packet;
- isolated independent first-pass execution;
- immutable Independent Submissions;
- anonymized Candidate transformation;
- randomized review order;
- structured evidence/assumption/confidence contract;
- one blind critique round;
- one private revision round;
- change-reason validation;
- Dissent Record and Minority Report;
- Diversity Snapshot;
- Conformity Signals and Alerts;
- fresh independent judge;
- explicit decision rubric;
- non-consensus outcomes;
- human approval;
- deliberation timeline UI;
- full provenance.

Gate:

```text
Three resources independently analyze one BOM decision without seeing peers.
After anonymized critique, every opinion change is tied to evidence or a valid
logical correction. Minority evidence remains visible. A fresh judge produces
a rubric-based recommendation. A simulated unsupported majority-following
scenario raises a Conformity Alert and can spawn a fresh panel.
```

### Phase 6 — AI-assisted clarification and requirement baseline

Deliver:

- Vision Intake Skill;
- BOM Domain Clarifier Skill;
- Requirement Completeness Skill;
- recommendation review UI;
- accept/reject/edit behavior;
- human approval;
- exact Skill/model/provider provenance.

Gate:

```text
AI can recommend but cannot silently alter an approved baseline.
```

### Phase 7 — PM Again integration

Deliver:

- PM Again service identity;
- PM adapter;
- delivery-planning command;
- Artifact References;
- Trace Links;
- retries;
- idempotency;
- integration activity timeline;
- degraded/manual handoff state.

Gate:

```text
Approved Requirement → PM Feature references.
No shared DB.
```

### Phase 8 — QA Again integration

Deliver:

- QA Again service identity;
- QA adapter;
- quality-design command;
- Test Scenario/Test Case references;
- coverage summary;
- missing-rule feedback;
- traceability;
- degraded/manual handoff state.

Gate:

```text
Requirement → QA Test references.
QA remains owner of test assets and execution.
```

### Phase 9 — Defect, impact, fix, and retest loop

Deliver:

- defect intake;
- affected-artifact candidate mapping;
- Defect Triage Skill;
- Impact Analysis Skill;
- fix proposal;
- PM notification;
- retest request;
- QA result intake;
- closure decision;
- full timeline.

Gate:

```text
Defect → Impact → Fix → Retest → Closure is complete and auditable.
```

### Phase 10 — Hardening and handover

Deliver:

- threat model;
- security review;
- provider-policy tests;
- Skill sandbox/permission review;
- anti-convergence benchmark and red-team report;
- conformity and diversity-collapse threshold tuning;
- judge independence audit;
- R2 lifecycle, quota, and private-access review;
- Workers AI quota/fallback test;
- Turnstile abuse-flow review;
- Web Analytics privacy review;
- backup/restore;
- capacity document;
- PostgreSQL migration trigger criteria;
- audit export;
- user guide;
- administrator guide;
- deployment guide;
- integration guide;
- Skill-authoring guide;
- provider-adapter guide;
- operational runbook;
- final handover.

---

## 18. Quality strategy

### 18.1 Backend

Required:

```bash
ruff check .
pytest
```

Test:

- auth;
- role enforcement;
- refresh rotation;
- project isolation;
- revision immutability;
- state transitions;
- idempotency;
- outbox/inbox;
- retry;
- Skill manifest validation;
- Skill version pinning;
- revocation;
- provider routing;
- budget enforcement;
- secret redaction;
- provenance;
- human approval gates;
- R2 object authorization and checksum verification;
- backup encryption and restore;
- Turnstile server verification;
- panel diversity constraints;
- independent-round isolation;
- anonymization;
- opinion-revision cause validation;
- Dissent Record preservation;
- conformity alerts;
- independent judge assignment.

### 18.2 Frontend

Required:

```bash
npm run lint
npm run build
```

Test:

- auth flows;
- route protection;
- project shell;
- Vision and Requirement revisions;
- recommendation review;
- Skill catalog;
- assignment and version display;
- provider status;
- cost/usage states;
- cross-app traceability;
- workflow timeline;
- permission states;
- error and retry states;
- private object upload/download;
- deliberation panel timeline;
- independent vs revised answer comparison;
- dissent and minority report visibility;
- diversity and conformity alerts;
- judge rubric;
- analytics privacy behavior.

### 18.3 Contract tests

Create contract fixtures for:

```text
Conductor ↔ PM Again
Conductor ↔ QA Again
Conductor ↔ Skill Runtime
Conductor ↔ AI Provider Adapter
Conductor ↔ Cloudflare R2
Conductor ↔ Cloudflare Turnstile
Conductor ↔ Deliberation Panel Runtime
```

Validate schemas and idempotency.

### 18.4 Golden-flow acceptance test

The Production BOM circular-reference flow must be repeatable from a clean project and produce:

- approved requirement baseline;
- PM references;
- QA references;
- complete trace links;
- failed test/defect reference;
- impact recommendation;
- fix reference;
- retest reference;
- human closure decision;
- complete provenance;
- independent multi-agent review for at least one high-impact requirement;
- preserved minority report;
- fresh judge recommendation;
- no unresolved Conformity Alert hidden from the final decision.

---

## 19. Security and threat-model requirements

At minimum review:

- JWT theft;
- refresh-token replay;
- CSRF;
- CORS mistakes;
- privilege escalation;
- cross-project access;
- SQL injection;
- path traversal;
- SSRF through integration endpoints;
- webhook spoofing;
- event replay;
- command duplication;
- malicious Skill package;
- Skill dependency confusion;
- unauthorized Skill publication;
- prompt injection;
- tool abuse;
- data exfiltration to an external model;
- secret leakage in prompt/logs;
- provider-key theft;
- budget exhaustion;
- denial of wallet;
- unsafe fallback to a prohibited provider;
- model-output schema bypass;
- false AI provenance;
- fake machine assertion;
- audit tampering;
- backup exposure;
- public R2 object exposure;
- pre-signed URL leakage;
- malicious object upload;
- object-key/path confusion;
- Turnstile token replay or action mismatch;
- analytics leakage through sensitive URLs;
- majority manipulation;
- identity-driven sycophancy;
- authority bias;
- coordinated wrong-answer cascade;
- deliberate poisoning of peer context;
- diversity collapse;
- judge contamination;
- minority evidence suppression;
- long-running consensus drift.

Security rules:

- outbound integrations require allow-listed origins;
- credentials never appear in normal API responses;
- Skill packages are checksummed and optionally signed;
- tool permissions are explicit;
- provider policy is enforced server-side;
- model output is untrusted input until validated;
- external content is marked and isolated;
- approval cannot be bypassed by AI output;
- audit and provenance are append-oriented;
- destructive admin actions require confirmation and logging;
- R2 buckets remain private;
- object access is time-limited and authorized;
- Turnstile tokens are verified server-side;
- analytics never becomes a channel for sensitive project content;
- independent-round outputs remain isolated until the round closes;
- provider/model identity is hidden during blind review;
- consensus summaries cannot silently become canonical facts;
- dissent cannot be deleted merely because a decision was approved.

---

## 20. Explicit non-goals for the MVP

```text
No Dev Again full product
No shared SSO across all Again Apps
No shared database
No Kafka
No Kubernetes
No microservice decomposition
No ungoverned autonomous multi-agent swarm
No general AI chat playground
No browser-cookie reuse
No consumer-subscription scraping
No unofficial or entitlement-violating provider automation
No visual workflow designer
No Skill marketplace payments
No third-party public Skill marketplace
No automatic production deployment
No AI final authority
No replacement of PM Again or QA Again
No full Production BOM/ERP implementation
```

---

## 21. Documentation required before final acceptance

```text
README.md
docs/ARCHITECTURE.md
docs/DOMAIN_OWNERSHIP.md
docs/DEPLOYMENT.md
docs/LOCAL_DEVELOPMENT.md
docs/AUTHENTICATION.md
docs/INTEGRATION_CONTRACTS.md
docs/WORKFLOW_STATE_MACHINE.md
docs/TRACEABILITY_MODEL.md
docs/SKILL_ARCHITECTURE.md
docs/SKILL_AUTHORING_GUIDE.md
docs/SKILL_DISTRIBUTION.md
docs/AI_PROVIDER_GATEWAY.md
docs/AI_RESOURCE_POOL.md
docs/AI_ENTITLEMENTS.md
docs/AI_ROUTING_POLICY.md
docs/AI_ROUTING_EXPLAINABILITY.md
docs/AI_ACCOUNT_ALLOCATION.md
docs/LOCAL_MODEL_RUNTIME.md
docs/CLOUDFLARE_SERVICE_LAYER.md
docs/R2_OBJECT_STORAGE.md
docs/R2_BACKUP_AND_RESTORE.md
docs/WORKERS_AI_ADAPTER.md
docs/TURNSTILE_INTEGRATION.md
docs/WEB_ANALYTICS_PRIVACY.md
docs/MULTI_AGENT_DELIBERATION.md
docs/ANTI_CONVERGENCE_POLICY.md
docs/DIVERSITY_AND_CONFORMITY_METRICS.md
docs/DISSENT_AND_MINORITY_REPORTS.md
docs/INDEPENDENT_JUDGE_PROTOCOL.md
docs/PROVIDER_CREDENTIALS.md
docs/PROVENANCE_AND_DECISIONS.md
docs/THREAT_MODEL.md
docs/BACKUP_AND_RESTORE.md
docs/CAPACITY_AND_POSTGRES_EXIT.md
docs/OPERATIONS_RUNBOOK.md
docs/USER_GUIDE.md
docs/ADMIN_GUIDE.md
docs/HANDOVER.md
```

---

## 22. Definition of done

Conductor Again MVP is done only when:

1. It is deployed end-to-end.
2. Authentication and project isolation work.
3. Manual Vision-to-Requirement workflow works without AI.
4. Skill Registry publishes immutable versions stored in private R2.
5. Skill assignments and revocations are traceable.
6. Private object upload/download uses authorized, short-lived access.
7. Encrypted SQLite backup to R2 and restore are tested.
8. Turnstile server verification works for selected abuse-sensitive flows.
9. Web Analytics is limited by an approved privacy boundary.
10. All known approved AI accounts, official subscription tools, Workers AI,
    and local runtimes can be registered with truthful Access Modes and
    Entitlements.
11. Normal AI work defaults to AUTO and does not require a
    provider/account/model choice from the user.
12. At least one official API route, one Workers AI route, one local-model
    route, one mock/test route, and one manual-handoff route work.
13. The router evaluates the registered pool, records rejected candidates,
    selects a Primary, prepares a Fallback Chain, and explains the decision.
14. Account concurrency, quota, budget, and Execution Leases are enforced.
15. High-impact work can trigger a diverse multi-agent panel.
16. Panel members produce isolated independent first-pass submissions.
17. Blind review removes provider/model/account identity and randomizes order.
18. Opinion revisions preserve originals and cite evidence or valid reasoning
    for every material change.
19. Dissent and minority evidence remain visible after a decision.
20. Conformity and diversity-collapse signals are calculated and auditable.
21. A simulated unsupported majority-following case raises an alert.
22. A fresh judge evaluates anonymized candidates against a fixed rubric.
23. The system can return unresolved disagreement or request more evidence
    instead of forcing consensus.
24. AI output is always marked as recommendation unless another proven actor
    type applies.
25. Routing and deliberation enforce data, cost, capability, entitlement,
    diversity, and project policies.
26. PM Again integration creates or imports delivery references without a
    shared DB.
27. QA Again integration creates or imports quality references without a
    shared DB.
28. Cross-app traceability is visible.
29. The circular-BOM defect/retest workflow works end-to-end.
30. Every important result has provenance.
31. Human approval gates cannot be bypassed.
32. Quality commands pass.
33. Documentation and handover are complete.

---

## 23. First message for a fresh Codex or coding-agent session

Paste this full document, then add:

> Clone and inspect PM Again first. Inspect the real QA Again repository available in the workspace or provide a clear blocker if it is missing. Before writing any feature code, confirm back the actual PM Again and QA Again conventions for authentication, database provisioning, routing, activity history, frontend layout, revision immutability, evidence/provenance, and deployment. Then complete Phase 0 only: repository audit, domain ownership matrix, ADR-001 through ADR-023, integration contract draft, Skill package draft, AI provider access-mode policy, Cloudflare service-layer plan, R2 storage contract, anti-convergence protocol, threat-model draft, and final MVP boundary. Do not start Phase 1 until Phase 0 is reviewed.

---

## 24. Final architectural principles

- Conductor Again is the control plane, not the whole platform.
- PM Again, QA Again, and external development systems retain domain ownership.
- Conductor owns Vision, canonical Requirement Baselines, cross-app decisions, and traceability.
- Conductor distributes and governs Skills.
- A Skill is versioned, testable, policy-bound, and more than a prompt.
- Skill execution may occur in Conductor, a target app, a local agent, or an approved external tool.
- Register all approved API accounts, official subscription-backed tools, and local runtimes in one AI Resource Pool.
- AUTO is the normal selection mode; users should not have to choose a provider, account, or model per task.
- Consumer subscriptions, API billing accounts, runtimes, models, and entitlements are distinct concepts.
- Use official provider access only; unsupported accounts remain manual rather than becoming fake APIs.
- Support OpenAI, Gemini, Claude, coding tools, and local models through adapters and policy, not hard-coded assumptions.
- Skills request capabilities; the router evaluates the whole eligible pool and chooses a Primary, Fallback Chain, and optional Escalation resource.
- Every routing decision must explain which resources were considered, rejected, scored, selected, or used as fallback.
- Multiple accounts are used for governed allocation and continuity, never for quota evasion.
- Multiple providers do not automatically create independent thinking.
- High-impact panels begin with isolated independent submissions.
- Peer review is anonymized and order-randomized.
- Consensus is an allowed outcome, not the target.
- Dissent, minority evidence, and original opinions are preserved.
- Every material opinion change must identify new evidence, corrected facts, changed assumptions, or valid critique.
- A fresh independent judge evaluates evidence and criteria, not provider reputation.
- Conformity, authority bias, and diversity collapse are monitored as operational risks.
- Long-running workflows periodically reset from source artifacts rather than inheriting only previous AI summaries.
- Cloudflare R2 stores private objects and immutable packages; it does not replace the transactional database.
- Cloudflare Workers AI is one governed Resource Pool member, not the platform's decision authority.
- Turnstile complements authentication and rate limiting; it does not replace them.
- Web Analytics must never receive sensitive project content.
- Rule engines handle deterministic decisions.
- Small/local models handle bounded tasks.
- Large models are used only when complexity warrants them.
- AI is a recommendation source, not the final authority.
- Human, Rule, Skill, AI, Machine, Application, and System provenance must remain distinguishable.
- Published requirements, decisions, and Skill versions require immutable history.
- Every work item must trace back to a Vision, Requirement, Defect, Risk, or Decision.
- The MVP must stay small enough to finish and strong enough to prove the complete value chain.
