# OIDA 1.0

OIDA 1.0 is the first frozen production baseline of the AI-ready, human-led project delivery workspace. It composes Document, PM, QA, Infra, Account, and Conductor services without taking ownership of their domain truth.

## What shipped

- Explicit project bindings and honest cross-service Project Truth.
- Project Attention, Command Center, Daily Briefing, and Portfolio Command Center.
- Governed, versioned deliverables with readiness prechecks, evidence snapshots, reviewer change briefs, and immutable signed/baselined history.
- Change and one-hop Impact Intelligence with EXPLICIT, DETERMINISTIC, AI_SUGGESTED, and UNKNOWN kept distinct.
- Human impact confirmation, two allowlisted low-risk owner action routes, read-after-write reconciliation, deterministic Resolution, and Resolution Intelligence.
- Grounded AI Reviewer, Project/Portfolio Copilots, Daily Briefing AI, and Resolution Assistant with deterministic fallbacks.
- Per-user project and portfolio review checkpoints, authorization isolation, audit, and provenance.

## How OIDA works

Truth stays with the bounded owner. OIDA composes and explains it, lets a human confirm context, previews controlled actions, calls the owner API only after explicit execution, refreshes truth, and evaluates resolution from evidence. Action success is not resolution; resolution is not customer acceptance.

## Human control and AI boundaries

Humans approve, acknowledge, accept, sign, waive, confirm, and execute. AI can explain and suggest from cited evidence. It cannot perform those decisions or writes. Provider absence or failure leaves the deterministic product available.

## Production validation

R19 dogfooded the real True Cloud Migration project and froze three golden scenarios. The release baseline has zero remaining P0/P1 defects. Document Again release 31 and OIDA Web deployment `c56491ef` are healthy; CI run `32569954808` passed for the accepted R19 head.

## Known operational gaps

- Fresh authenticated browser and multi-device checkpoint replay.
- Production AI provider configuration and authorized-evidence smoke test.
- Disposable authenticated PM/QA mutation target for production action dogfood.
- Genuine multi-project Portfolio dogfood.
- Owner deep-link SSO continuity and narrow-screen sidebar follow-up.

These are isolated operations/usage items, not hidden product acceptance claims. No autonomous remediation, high-risk Infra mutation, scheduled notification, or automatic customer acceptance is included.

After OIDA 1.0, feature work stops until justified by real usage, dogfood evidence, a high-value goal, an operational need, or a security/governance requirement.
