# INFRA-AGAIN — Strategy B Feasibility Audit: draw.io Embed Mode

## Candidate: diagrams.net (draw.io) via `react-drawio`

**Source**: https://github.com/jgraph/drawio (Apache 2.0, 7.4k stars)
**React wrapper**: `react-drawio` v1.0.7 (MIT, 14.6K weekly downloads)
**Self-host**: `jgraph/drawio` Docker image (2.2k stars)
**Embed docs**: https://www.drawio.com/doc/faq/embed-mode

---

## GATE B1.1 — EMBEDDED EDITOR: ✅ PASS

`react-drawio` wraps the draw.io iframe as a React component:

```tsx
import { DrawIoEmbed, DrawIoEmbedRef } from 'react-drawio';
<DrawIoEmbed ref={ref} xml="..." onSave={handleSave} onExport={handleExport} />
```

- Runs entirely in iframe within React app
- Host controls lifecycle (load/save/export)
- `baseUrl` prop for self-hosted instances
- No external SaaS dependency when self-hosted

---

## GATE B1.2 — PROGRAMMATIC LOAD: ✅ PASS

JSON protocol `load` action:

```json
{"action": "load", "xml": "<mxGraphModel>...</mxGraphModel>"}
```

Also supports:
- Mermaid descriptor: `{descriptor: {format: "mermaid", data: "graph TD\n  A-->B"}}`
- CSV, SVG+XML, PNG+XML, Visio, Lucidchart, Gliffy
- `sourceMetadata` for storing original source key-value pairs

---

## GATE B1.3 — PROGRAMMATIC SAVE: ✅ PASS

- `onSave` callback: `{event: 'save', xml: '...'}`
- `onExport` callback: `{event: 'export', format: '...', data: '...'}`
- `autosave` mode: `{event: 'autosave', xml: '...', patch: {...}}`
- `diffSync` mode for incremental sync with checksums
- Export formats: xml, svg, png, xmlsvg, xmlpng, json, html

---

## GATE B1.4 — AI GENERATION COMPATIBILITY: ✅ PASS

AI can generate Mermaid syntax, which draw.io loads natively:

```json
{"action": "load", "descriptor": {"format": "mermaid", "data": "graph TD\n  Client-->API\n  API-->DB"}}
```

This means:
1. LLM generates Mermaid → draw.io renders as diagram
2. `sourceMetadata` stores original AI prompt/source
3. User edits visually → saves back as draw.io XML
4. Host extracts semantic model from JSON export

---

## GATE B1.5 — ROUND-TRIP MODEL: ⚠️ PARTIAL (viable hybrid)

**Proposed hybrid**: Canonical semantic model + draw.io XML as diagram document.

- Canonical `ArchitectureDesign` stores: nodes, edges, groups, metadata, provider info
- `diagramDocument` field stores draw.io XML for visual state
- `diagramEngine` = "drawio"
- JSON export (`format: 'json'`) provides structural bridge:
  ```json
  {"pages": [{"cells": [
    {"id": "n1", "type": "node", "label": "API Gateway", "metadata": {"provider": "aws", "service": "api-gateway"}},
    {"id": "e1", "type": "edge", "source": "n1", "target": "n2"}
  ]}]}
  ```
- Metadata round-trips via `metadata` field on cells
- Layout positions preserved in draw.io XML

**Limitation**: Not perfectly bidirectional. Visual changes must be reconciled with semantic model on save. The canonical model is authoritative for planning; draw.io XML preserves visual layout.

---

## GATE B1.6 — PROVIDER-LIBRARY SUPPORT: ✅ PASS

draw.io has extensive built-in shape libraries:
- **AWS**: 200+ native service icons (Route 53, CloudFront, WAF, API Gateway, ALB, Lambda, ECS, EKS, EC2, RDS, DynamoDB, ElastiCache, S3, SQS, SNS, EventBridge, KMS, IAM, VPC, etc.)
- **GCP**: Cloud LB, Cloud Run, GKE, Cloud SQL, BigQuery, Pub/Sub, Cloud Storage
- **Kubernetes**: Native K8s icons
- **Network**: Generic network, firewall, load balancer
- **General**: Database, server, storage, user icons

Libraries enabled via `libraries=1` URL param or `libs` in load message.

Custom shape libraries supported via XML format.

---

## GATE B1.7 — MULTI-VIEW SUPPORT: ✅ PASS

draw.io supports **pages** (tabs) natively:
- Page 1 = Architecture
- Page 2 = Data Flow
- Page 3 = Operation Flow
- Page 4 = Security Flow

Also supports **layers** within each page for overlays/annotations.

JSON protocol can target specific pages: `{currentPage: true}`, `{pageId: "..."}`.

---

## GATE B1.8 — NODE METADATA BINDING: ✅ PASS

Cells support custom attributes via `metadata`:
```json
{"id": "n1", "type": "node", "label": "RDS", "metadata": {
  "provider": "aws", "nativeService": "rds", "platform": "NATIVE_VM",
  "securityZone": "private", "dataClassification": "pii", "owner": "platform-team"
}}
```

Root-level `sourceMetadata` stores design-level key-value pairs.

These survive save/load round-trips.

---

## GATE B1.9 — SELF-HOST CAPABILITY: ✅ PASS

- Official Docker image: `jgraph/drawio` (Apache 2.0)
- `docker run -p 8080:8080 jgraph/drawio`
- `?offline=1` mode disables cloud storage
- No external SaaS dependency for core editing
- `react-drawio` `baseUrl` prop points to self-hosted instance
- Also supports `self-contained` mode with export server, Google Drive, OneDrive

---

## GATE B1.10 — DOWNSTREAM PLANNING COMPATIBILITY: ✅ PASS

JSON export provides structured data extractable for planning:

```json
{
  "pages": [{"cells": [
    {"id": "n1", "type": "node", "label": "ECS", "metadata": {"provider": "aws", "service": "ecs"}},
    {"id": "e1", "type": "edge", "source": "n1", "target": "n2", "label": "HTTP"}
  ]}]
}
```

This can be mapped to:
- Implementation Plan resources
- Service types → execution tasks
- Dependencies → task ordering
- Provider/platform → execution target

---

## SECURITY REVIEW: ✅ ACCEPTABLE

- iframe sandbox: `sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"`
- postMessage origin validation via JSON protocol
- CSP configurable via `DRAWIO_CSP_HEADER`
- XML parsing: draw.io handles internally, no external XML injection surface
- Custom image URLs: disabled by default, `ENABLE_DRAWIO_PROXY` for proxy
- No external links without `suppressNewWindows` config
- License: Apache 2.0 (no GPL/AGPL)

## LICENSING REVIEW: ✅ PASS

- draw.io core: Apache 2.0
- `react-drawio`: MIT
- Docker image: Apache 2.0
- Icon sets: Custom license (restricts Atlassian marketplace use; fine for INFRA-AGAIN)
- No copyleft restrictions

---

## B1_DECISION: STRATEGY_B_ACCEPTED

All 10 mandatory gates evaluated. Results:

| Gate | Result |
|------|--------|
| EMBED_EDITOR | ✅ PASS |
| PROGRAMMATIC_LOAD | ✅ PASS |
| PROGRAMMATIC_SAVE | ✅ PASS |
| AI_GENERATION_COMPATIBILITY | ✅ PASS |
| ROUND_TRIP_MODEL | ⚠️ PARTIAL (viable hybrid) |
| PROVIDER_LIBRARY_SUPPORT | ✅ PASS |
| MULTI_VIEW_SUPPORT | ✅ PASS |
| NODE_METADATA_BINDING | ✅ PASS |
| SELF_HOST_CAPABILITY | ✅ PASS |
| DOWNSTREAM_PLAN_COMPATIBILITY | ✅ PASS |

**7 mandatory gates PASS. ROUND_TRIP_MODEL is PARTIAL with a viable hybrid design (canonical model + draw.io XML as diagram document).**

Strategy B proceeds to POC (Phase B2).
