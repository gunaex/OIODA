import React from "react";
import { Background, Controls, MiniMap, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

/*
 * Shared React Flow diagram primitives. Only what is genuinely common across
 * the ERD / Process Flow / Architecture workspaces lives here: the canvas
 * shell (background, controls, minimap) and layout persistence. Domain-
 * specific node behavior stays in each workspace's own node component.
 */
export function DiagramCanvas({ nodes, edges, nodeTypes, onNodesChange, height = 320, fitView = true }) {
  return (
    <div style={{ height }} className="overflow-hidden rounded border border-line bg-surface-0">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        fitView={fitView}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e2433" gap={18} />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}

/**
 * Apply React Flow node-change position deltas into a semantic-id-keyed
 * layout object and report whether a drag finished (=> persist).
 */
export function applyPositionChanges(changes, prev) {
  const next = { ...prev };
  let persisted = false;
  for (const c of changes) {
    if (c.type === "position" && c.position) {
      next[c.id] = { x: c.position.x, y: c.position.y };
    }
    if (c.type === "position" && c.dragging === false) persisted = true;
  }
  return { layout: next, persisted };
}
