"""Infra Pulse + Design Review API Routes.

Phase 5.0.1: Design lifecycle with SQLite persistence for restart durability.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .models import (
    DesignBaseline, DesignStatus, FlowDefinition, FlowPlaybackState,
    ScenarioId, MetricSource, SimulationMode, FlowEvent,
)
from .simulator import FlowSimulator, create_demo_flow
from .reducer import reduce_state

# ============================================================================
# Persistence
# ============================================================================

import os as _os
DB_PATH = _os.environ.get("INFRA_AGAIN_DB", str(Path(".ai/infra-again.db").resolve()))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flow_designs (
            design_id TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            revision INTEGER DEFAULT 1,
            status TEXT DEFAULT 'DRAFT',
            requirements_checksum TEXT DEFAULT '',
            architecture_checksum TEXT DEFAULT '',
            flow_checksum TEXT DEFAULT '',
            flow_json TEXT DEFAULT '',
            accepted_at TEXT DEFAULT '',
            accepted_by TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flow_design_change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            design_id TEXT NOT NULL,
            comment TEXT DEFAULT '',
            node_id TEXT DEFAULT '',
            severity TEXT DEFAULT 'INFO',
            timestamp TEXT DEFAULT '',
            FOREIGN KEY (design_id) REFERENCES flow_designs(design_id)
        )
    """)
    conn.commit()


def _persist_design(design: DesignBaseline, flow: FlowDefinition | dict | None = None) -> None:
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        flow_json = ""
        if flow:
            if hasattr(flow, 'to_dict'):
                flow_json = json.dumps(flow.to_dict())
            elif isinstance(flow, dict):
                flow_json = json.dumps(flow)
        conn.execute("""
            INSERT OR REPLACE INTO flow_designs
            (design_id, name, description, revision, status,
             requirements_checksum, architecture_checksum, flow_checksum, flow_json,
             accepted_at, accepted_by, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            design.design_id,
            design.metadata.get("name", ""),
            design.metadata.get("description", ""),
            design.revision,
            design.status.value,
            design.requirements_checksum,
            design.architecture_checksum,
            design.flow_checksum,
            flow_json,
            design.accepted_at,
            design.accepted_by,
            design.created_at or now,
            now,
        ))
        # Persist change requests
        conn.execute("DELETE FROM flow_design_change_requests WHERE design_id=?", (design.design_id,))
        for cr in design.change_requests:
            conn.execute("""
                INSERT INTO flow_design_change_requests (design_id, comment, node_id, severity, timestamp)
                VALUES (?,?,?,?,?)
            """, (design.design_id, cr.get("comment", ""), cr.get("nodeId", ""),
                  cr.get("severity", "INFO"), cr.get("timestamp", "")))
        conn.commit()
    finally:
        conn.close()


def _load_design(design_id: str) -> DesignBaseline | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM flow_designs WHERE design_id=?", (design_id,)).fetchone()
        if not row:
            return None
        design = DesignBaseline(
            design_id=row["design_id"],
            revision=row["revision"],
            status=DesignStatus(row["status"]) if row["status"] else DesignStatus.DRAFT,
            requirements_checksum=row["requirements_checksum"] or "",
            architecture_checksum=row["architecture_checksum"] or "",
            flow_checksum=row["flow_checksum"] or "",
            accepted_at=row["accepted_at"] or "",
            accepted_by=row["accepted_by"] or "",
            created_at=row["created_at"] or "",
            metadata={"name": row["name"] or "", "description": row["description"] or ""},
        )
        # Load change requests
        crs = conn.execute(
            "SELECT * FROM flow_design_change_requests WHERE design_id=? ORDER BY id", (design_id,)
        ).fetchall()
        design.change_requests = [
            {"comment": cr["comment"], "nodeId": cr["node_id"],
             "severity": cr["severity"], "timestamp": cr["timestamp"]}
            for cr in crs
        ]
        return design
    finally:
        conn.close()


def _load_all_designs() -> list[DesignBaseline]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT design_id FROM flow_designs ORDER BY updated_at DESC").fetchall()
        designs = []
        for r in rows:
            d = _load_design(r["design_id"])
            if d:
                designs.append(d)
        return designs
    finally:
        conn.close()


def _load_design_flow(design_id: str) -> FlowDefinition | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT flow_json FROM flow_designs WHERE design_id=?", (design_id,)).fetchone()
        if row and row["flow_json"]:
            data = json.loads(row["flow_json"])
            return _reconstruct_flow(data)
        return None
    finally:
        conn.close()


def _reconstruct_flow(data: dict) -> FlowDefinition:
    """Reconstruct FlowDefinition from persisted JSON."""
    from .models import FlowNode, FlowEdge, FlowType, NodeCategory, FlowNodeState, FlowEdgeState
    nodes = []
    for nd in data.get("nodes", []):
        cat = nd.get("category", "APPLICATION")
        nodes.append(FlowNode(
            node_id=nd.get("nodeId", ""), label=nd.get("label", ""),
            description=nd.get("description", ""),
            category=NodeCategory(cat) if cat in NodeCategory._value2member_map_ else NodeCategory.APPLICATION,
            provider=nd.get("provider", ""), platform=nd.get("platform", ""),
            state=FlowNodeState.IDLE,
            position=nd.get("position", {"x": 0, "y": 0}),
            group_id=nd.get("groupId", ""),
        ))
    edges = []
    for ed in data.get("edges", []):
        ft = ed.get("flowType", "REQUEST")
        edges.append(FlowEdge(
            edge_id=ed.get("edgeId", ""), source_id=ed.get("sourceId", ""),
            target_id=ed.get("targetId", ""),
            flow_type=FlowType(ft) if ft in FlowType._value2member_map_ else FlowType.REQUEST,
            state=FlowEdgeState.IDLE, label=ed.get("label", ""),
        ))
    return FlowDefinition(
        flow_id=data.get("flowId", ""), name=data.get("name", ""),
        flow_type=FlowType.REQUEST, architecture_graph_id=data.get("architectureGraphId", ""),
        entry_node_id=data.get("entryNodeId", ""), nodes=nodes, edges=edges,
        groups=data.get("groups", []),
    )


# ============================================================================
# In-memory caches (backed by SQLite)
# ============================================================================

_designs: dict[str, DesignBaseline] = {}
_flows: dict[str, FlowDefinition] = {}
_simulations: dict[str, dict[str, Any]] = {}


def _load_all_from_db() -> None:
    """Load persisted designs into memory cache on startup."""
    for d in _load_all_designs():
        _designs[d.design_id] = d
        flow = _load_design_flow(d.design_id)
        if flow:
            _flows[flow.flow_id] = flow


def register_flow_routes(app: FastAPI) -> None:
    """Register all Phase 5 flow/design routes on an existing FastAPI app."""

    # Load persisted state on startup
    _load_all_from_db()

    # ------------------------------------------------------------------
    # Designs
    # ------------------------------------------------------------------

    @app.get("/api/v1/designs")
    async def list_designs():
        return {"designs": [d.to_dict() for d in _designs.values()], "count": len(_designs)}

    @app.post("/api/v1/designs")
    async def create_design(name: str = "", description: str = ""):
        # DesignBaseline's default factory mints a uuid4-based id. The
        # previous `f"DESIGN-{len(_designs)+1:06d}"` counter was not atomic —
        # two concurrent creates can compute the same id, and _persist_design
        # uses INSERT OR REPLACE, so the second create would silently
        # overwrite the first design's row instead of erroring.
        design = DesignBaseline()
        design.metadata = {"name": name, "description": description}
        _designs[design.design_id] = design
        _persist_design(design)
        return {"design": design.to_dict()}

    @app.get("/api/v1/designs/{design_id}")
    async def get_design(design_id: str):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        result = d.to_dict()
        # Include stored flow data
        conn = _get_conn()
        try:
            row = conn.execute("SELECT flow_json FROM flow_designs WHERE design_id=?", (design_id,)).fetchone()
            if row and row["flow_json"]:
                result["flow"] = json.loads(row["flow_json"])
        finally:
            conn.close()
        return {"design": result}

    @app.get("/api/v1/designs/{design_id}/feasibility")
    async def get_design_feasibility(design_id: str, fidelity: str = "SIMULATED"):
        """Phase N2 — read-only architecture feasibility/executability for a
        persisted design, recomputed fresh from Provider Intelligence every
        call. Never trusts any executability-looking field the design's raw
        flow JSON might already carry."""
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        conn = _get_conn()
        try:
            row = conn.execute("SELECT flow_json FROM flow_designs WHERE design_id=?", (design_id,)).fetchone()
        finally:
            conn.close()
        flow_data = json.loads(row["flow_json"]) if row and row["flow_json"] else {}
        nodes = flow_data.get("nodes", [])

        from ..intelligence.feasibility import assess_architecture_feasibility
        provider = next((n.get("provider", "") for n in nodes if n.get("provider") not in ("", "EXTERNAL")), "")
        assessment = assess_architecture_feasibility(
            nodes, architecture_id=design_id, architecture_revision=str(d.revision),
            provider=provider, platform=flow_data.get("platform", ""),
            requested_fidelity=fidelity,
        )
        return {"feasibility": assessment.to_dict()}

    @app.post("/api/v1/designs/{design_id}/generate")
    async def generate_design(design_id: str):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        if d.status.value in ("ACCEPTED", "BASELINE_FROZEN"):
            raise HTTPException(status_code=400, detail={
                "error": "Cannot regenerate an accepted/frozen design",
                "status": d.status.value,
            })

        # Create demo flow for this design
        flow = create_demo_flow()
        flow.architecture_graph_id = design_id
        _flows[flow.flow_id] = flow

        # Compute checksums
        d.requirements_checksum = hashlib.sha256(
            json.dumps({"designId": design_id}, sort_keys=True).encode()
        ).hexdigest()[:16]
        d.architecture_checksum = hashlib.sha256(
            json.dumps([n.to_dict() for n in flow.nodes], sort_keys=True).encode()
        ).hexdigest()[:16]
        d.flow_checksum = hashlib.sha256(
            json.dumps([e.to_dict() for e in flow.edges], sort_keys=True).encode()
        ).hexdigest()[:16]
        d.status = DesignStatus.REVIEW_READY

        _persist_design(d, flow)

        return {
            "design": d.to_dict(),
            "flow": flow.to_dict(),
        }

    @app.get("/api/v1/designs/{design_id}/architecture")
    async def get_design_architecture(design_id: str):
        flows = [f for f in _flows.values() if f.architecture_graph_id == design_id]
        if not flows:
            raise HTTPException(status_code=404, detail="No flows for this design")
        return {"designId": design_id, "flows": [f.to_dict() for f in flows]}

    @app.get("/api/v1/designs/{design_id}/flows")
    async def get_design_flows(design_id: str):
        flows = [f for f in _flows.values() if f.architecture_graph_id == design_id]
        return {"designId": design_id, "flows": [f.to_dict() for f in flows], "count": len(flows)}

    @app.post("/api/v1/designs/{design_id}/simulate")
    async def simulate_design(design_id: str, scenario: str = "HAPPY_PATH", flow_id: str = "", seed: int = 42):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")

        flow = _flows.get(flow_id) if flow_id else None
        if not flow:
            flows = [f for f in _flows.values() if f.architecture_graph_id == design_id]
            flow = flows[0] if flows else None
        if not flow:
            raise HTTPException(status_code=404, detail="No flow for this design. Call /generate first.")

        sim = FlowSimulator(flow=flow, scenario=scenario, seed=seed)
        events = sim.simulate()
        bottlenecks = sim.get_bottlenecks()
        final_state = reduce_state(flow, events, bottlenecks=bottlenecks)

        sim_id = f"sim-{design_id}-{scenario}-{seed}"
        sim_result = {
            "simulationId": sim_id,
            "designId": design_id,
            "flowId": flow.flow_id,
            "scenario": scenario,
            "source": "SIMULATED",
            "durationMs": events[-1].timestamp_ms if events else 0,
            "events": [e.to_dict() for e in events],
            "bottlenecks": [b.to_dict() for b in bottlenecks],
            "finalState": final_state.to_dict(),
        }
        _simulations[sim_id] = sim_result
        return sim_result

    @app.post("/api/v1/designs/{design_id}/accept")
    async def accept_design(design_id: str, accepted_by: str = ""):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        if d.status not in (DesignStatus.DRAFT, DesignStatus.GENERATED, DesignStatus.REVIEW_READY, DesignStatus.USER_REVIEW):
            raise HTTPException(status_code=400, detail=f"Cannot accept design in status {d.status.value}")
        d.accept(accepted_by)
        # Preserve flow data from DB if no in-memory flow exists
        flow = next((f for f in _flows.values() if f.architecture_graph_id == design_id), None)
        if not flow:
            conn = _get_conn()
            try:
                row = conn.execute("SELECT flow_json FROM flow_designs WHERE design_id=?", (design_id,)).fetchone()
                if row and row["flow_json"]:
                    import json
                    flow = json.loads(row["flow_json"])
            finally:
                conn.close()
        _persist_design(d, flow)
        return {"design": d.to_dict(), "note": "No real infrastructure will be created by this action."}

    @app.post("/api/v1/designs/{design_id}/request-change")
    async def request_change(design_id: str, comment: str = "", node_id: str = "", severity: str = "INFO"):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        d.request_change(comment, node_id, severity)
        flow = next((f for f in _flows.values() if f.architecture_graph_id == design_id), None)
        _persist_design(d, flow)
        return {"design": d.to_dict()}

    @app.post("/api/v1/designs/{design_id}/ai-generate")
    async def ai_generate_design(design_id: str, body: dict[str, Any] | None = None):
        """AI-assisted architecture generation from a design brief."""
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        if d.status.value in ("ACCEPTED", "BASELINE_FROZEN"):
            raise HTTPException(status_code=400, detail={
                "error": "Cannot regenerate an accepted/frozen design",
                "status": d.status.value,
            })
        brief = (body or {}).get("brief", {})
        provider = brief.get("provider", "AWS")
        platform = brief.get("platform", "KUBERNETES")
        objective = brief.get("objective", "")
        components = brief.get("components", "")
        import uuid, json
        nodes, edges = [], []
        prev_id = "entry"
        nodes.append({"id":"entry","type":"input","position":{"x":300,"y":0},"data":{"label":"User / Client","category":"USER","provider":provider}})
        if provider == "AWS":
            svcs = [("waf","WAF/Shield","SECURITY",0),("cf","CloudFront","NETWORK",70),("alb","ALB","NETWORK",140),("gw","API Gateway","GATEWAY",210),("lambda","Lambda","APPLICATION",280),("ecs","ECS/Fargate","APPLICATION",350),("rds","RDS","DATABASE",420),("elasticache","ElastiCache","CACHE",490),("s3","S3","STORAGE",560),("sqs","SQS","QUEUE",630),("kms","KMS","SECURITY",700)]
        elif provider == "GCP":
            svcs = [("clb","Cloud LB","NETWORK",0),("cloudrun","Cloud Run","APPLICATION",100),("gke","GKE","APPLICATION",200),("cloudsql","Cloud SQL","DATABASE",300),("bigquery","BigQuery","DATABASE",400),("pubsub","Pub/Sub","QUEUE",500),("gcs","Cloud Storage","STORAGE",600)]
        else:
            svcs = [("app","App Server","APPLICATION",0),("k8s","Kubernetes","APPLICATION",120),("db","Database","DATABASE",240),("cache","Cache","CACHE",360),("storage","Storage","STORAGE",480),("lb","Load Balancer","NETWORK",600)]
        for sid,sl,sc,sy in svcs:
            nid = f"svc-{sid}"
            nodes.append({"id":nid,"position":{"x":300,"y":100+sy},"data":{"label":sl,"category":sc,"provider":provider}})
            edges.append({"id":f"e-{prev_id}-{nid}","source":prev_id,"target":nid,"label":"→","animated":True})
            prev_id = nid
        all_nids = [n["id"] for n in nodes]
        all_eids = [e["id"] for e in edges]
        arch_nids = [n["id"] for n in nodes if n["data"]["category"] not in ("OBSERVABILITY",)]
        data_nids = [n["id"] for n in nodes if n["data"]["category"] in ("DATABASE","STORAGE","QUEUE","CACHE")]
        ops_nids = [n["id"] for n in nodes if n["data"]["category"] in ("USER","NETWORK","GATEWAY","APPLICATION","SERVICE")]
        sec_nids = [n["id"] for n in nodes if n["data"]["category"] in ("SECURITY","IDENTITY")]
        flow_def = {"nodes":nodes,"edges":edges,"layers":{"architecture":{"nodes":arch_nids,"edges":all_eids},"dataFlow":{"nodes":data_nids,"edges":[]},"operationFlow":{"nodes":ops_nids,"edges":all_eids},"securityFlow":{"nodes":sec_nids,"edges":[]}},"rationale":f"AI-generated {provider} architecture on {platform}. {objective}"}
        _persist_design(d, flow_def)
        return {"designId":design_id,"flow":flow_def,"provider":provider,"platform":platform,"status":"AI_GENERATED"}

    @app.post("/api/v1/designs/{design_id}/update-flow")
    async def update_design_flow(design_id: str, body: dict[str, Any]):
        """Update graph flow for a design."""
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        if d.status.value in ("ACCEPTED", "BASELINE_FROZEN"):
            raise HTTPException(status_code=400, detail={"error": "Cannot edit accepted/frozen design"})
        flow = body.get("flow", {})
        _persist_design(d, flow)
        return {"designId": design_id, "status": "updated"}

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------

    @app.get("/api/v1/flows/{flow_id}")
    async def get_flow(flow_id: str):
        flow = _flows.get(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        return {"flow": flow.to_dict()}

    @app.get("/api/v1/flows/{flow_id}/events")
    async def get_flow_events(flow_id: str, scenario: str = "HAPPY_PATH", seed: int = 42):
        flow = _flows.get(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        sim = FlowSimulator(flow=flow, scenario=scenario, seed=seed)
        events = sim.simulate()
        return {"flowId": flow_id, "scenario": scenario, "events": [e.to_dict() for e in events]}

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    @app.get("/api/v1/scenarios")
    async def list_scenarios():
        from .simulator import SCENARIO_CONFIG
        return {
            "scenarios": [
                {"id": sid, "description": cfg["description"]}
                for sid, cfg in SCENARIO_CONFIG.items()
            ]
        }
