import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState,
  type Node, type Edge, MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './styles/infraPulse.css';
import PulseNode from './components/PulseNode';
import PulseEdge from './components/PulseEdge';
import FlowTimeline from './components/FlowTimeline';
import FlowScenarioSelector from './components/FlowScenarioSelector';
import FlowDetailsPanel from './components/FlowDetailsPanel';
import BottleneckPanel from './components/BottleneckPanel';
import DesignReviewPanel from './components/DesignReviewPanel';
import type {
  FlowDefinition, FlowPlaybackState, FlowEvent, SimulationResult,
  Design, DesignStatus, ScenarioId, FlowNodeState, FlowBottleneck,
} from './model/flowTypes';

const API = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_API_URL) || '';

const nodeTypes = { pulseNode: PulseNode };
const edgeTypes = { pulseEdge: PulseEdge };

// Layout: left-to-right
function layoutNodes(flow: FlowDefinition): Node[] {
  return flow.nodes.map((n, i) => ({
    id: n.nodeId,
    type: 'pulseNode',
    position: { x: i * 180 + 20, y: 120 + (i % 2) * 100 },
    data: {
      label: n.label,
      state: 'IDLE' as FlowNodeState,
      category: n.category,
      provider: n.provider,
      description: n.description,
    },
  }));
}

function layoutEdges(flow: FlowDefinition): Edge[] {
  return flow.edges.map((e) => ({
    id: e.edgeId,
    source: e.sourceId,
    target: e.targetId,
    type: 'pulseEdge',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
    data: { state: 'IDLE', flowType: e.flowType, label: e.label },
  }));
}

export default function InfraPulsePage() {
  const [design, setDesign] = useState<Design | null>(null);
  const [flow, setFlow] = useState<FlowDefinition | null>(null);
  const [simResult, setSimResult] = useState<SimulationResult | null>(null);
  const [events, setEvents] = useState<FlowEvent[]>([]);
  const [playbackMs, setPlaybackMs] = useState(-1);
  const [scenario, setScenario] = useState<ScenarioId>('HAPPY_PATH');
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [view, setView] = useState<'flow' | 'review'>('flow');
  const [loading, setLoading] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Create design
  const createDesign = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(API + '/api/v1/designs?name=Customer+API+Service', { method: 'POST' });
      const d = await r.json();
      const designId = d.design.designId;

      const g = await fetch(API + `/api/v1/designs/${designId}/generate`, { method: 'POST' });
      const gd = await g.json();
      setDesign(gd.design);
      setFlow(gd.flow);
      setNodes(layoutNodes(gd.flow));
      setEdges(layoutEdges(gd.flow));
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [API]);

  // Run simulation
  const runSim = useCallback(async (sc: ScenarioId) => {
    if (!design || !flow) return;
    setScenario(sc);
    setLoading(true);
    try {
      const r = await fetch(
        API + `/api/v1/designs/${design.designId}/simulate?scenario=${sc}&flowId=${flow.flowId}&seed=42`,
        { method: 'POST' }
      );
      const sr: SimulationResult = await r.json();
      setSimResult(sr);
      setEvents(sr.events);
      setPlaybackMs(-1);
      applyState(sr.finalState);
      setPlaying(false);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [design, flow, API]);

  // Apply playback state to nodes/edges
  const applyState = useCallback((state: FlowPlaybackState) => {
    setNodes((nds) => nds.map((n) => ({
      ...n,
      data: {
        ...n.data,
        state: state.nodeStates[n.id] || 'IDLE',
        latencyMs: state.bottlenecks?.find((b: FlowBottleneck) => b.nodeId === n.id)
          ? state.bottlenecks.find((b: FlowBottleneck) => b.nodeId === n.id)?.factors?.[0]?.value
          : undefined,
      },
    })));
    setEdges((eds) => eds.map((e) => ({
      ...e,
      data: { ...e.data, state: state.edgeStates[e.id] || 'IDLE' },
    })));
  }, []);

  // Playback stepping
  useEffect(() => {
    if (!playing || events.length === 0) return;
    const interval = setInterval(() => {
      setPlaybackMs((prev) => {
        const step = 50 / speed;
        const next = prev < 0 ? step : prev + step;
        const maxMs = events[events.length - 1]?.timestampMs || 0;
        if (next >= maxMs) {
          setPlaying(false);
          applyState(simResult?.finalState!);
          return maxMs;
        }
        // Find events at this timestamp
        const activeEvts = events.filter((e) => e.timestampMs <= next);
        if (activeEvts.length > 0) {
          // Reconstruct approximate state
          const nodeStates: Record<string, FlowNodeState> = {};
          const edgeStates: Record<string, any> = {};
          for (const evt of activeEvts) {
            if (evt.eventType === 'NODE_ENTER') nodeStates[evt.nodeId] = 'ACTIVE';
            if (evt.eventType === 'NODE_PASS') nodeStates[evt.nodeId] = 'PASS';
            if (evt.eventType === 'NODE_BLOCK') nodeStates[evt.nodeId] = 'BLOCKED';
            if (evt.eventType === 'NODE_FAIL') nodeStates[evt.nodeId] = 'FAILED';
            if (evt.eventType === 'APPROVAL_REQUESTED') nodeStates[evt.nodeId] = 'WAITING';
            if (evt.eventType === 'BOTTLENECK_DETECTED') nodeStates[evt.nodeId] = 'DEGRADED';
            if (evt.eventType === 'RETRY_START') nodeStates[evt.nodeId] = 'RETRYING';
          }
          applyState({
            flowId: flow?.flowId || '', timestampMs: next,
            nodeStates, edgeStates, activePath: [], bottlenecks: [],
            currentEvent: activeEvts[activeEvts.length - 1],
          });
        }
        return next;
      });
    }, 50 / speed);
    return () => clearInterval(interval);
  }, [playing, events, speed]);

  // Accept design
  const acceptDesign = useCallback(async () => {
    if (!design) return;
    const r = await fetch(API + `/api/v1/designs/${design.designId}/accept?accepted_by=user`, { method: 'POST' });
    const d = await r.json();
    setDesign(d.design);
  }, [design, API]);

  // Request change
  const requestChange = useCallback(async (comment: string) => {
    if (!design) return;
    const r = await fetch(
      API + `/api/v1/designs/${design.designId}/request-change?comment=${encodeURIComponent(comment)}`,
      { method: 'POST' }
    );
    const d = await r.json();
    setDesign(d.design);
  }, [design, API]);

  const scenarioList: ScenarioId[] = ['HAPPY_PATH','AUTH_FAILURE','FIREWALL_BLOCK','DATABASE_SLOW','API_TIMEOUT','APPROVAL_WAIT','RETRY_RECOVERY'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 60px)', background: '#1a1d23' }}>
      {/* Header */}
      <div className="pulse-header">
        <h2 className="pulse-header__title">Infra Pulse</h2>
        {!design ? (
          <button onClick={createDesign} disabled={loading} className="pulse-btn pulse-btn--primary">
            {loading ? 'Loading...' : 'Create Design'}
          </button>
        ) : (
          <>
            <span style={{ fontSize: 12, color: '#8b8fa3', fontFamily: 'monospace' }}>{design.designId}</span>
            <span className={`pulse-badge ${
              design.status === 'BASELINE_FROZEN' ? 'pulse-badge--frozen' :
              design.status === 'CHANGE_REQUESTED' ? 'pulse-badge--change' :
              design.status === 'REVIEW_READY' ? 'pulse-badge--review' : 'pulse-badge--draft'
            }`}>
              {design.status.replace(/_/g, ' ')}
            </span>
            <span className="pulse-sim-banner">⬤ SIMULATION</span>
          </>
        )}
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 4 }}>
          <button onClick={() => setView('flow')} className={`pulse-btn pulse-btn--sm ${view === 'flow' ? 'pulse-btn--primary' : 'pulse-btn--ghost'}`}>Flow</button>
          <button onClick={() => setView('review')} className={`pulse-btn pulse-btn--sm ${view === 'review' ? 'pulse-btn--primary' : 'pulse-btn--ghost'}`}>Design Review</button>
        </div>
      </div>

      {!design ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8b8fa3', fontSize: 14 }}>
          Click <strong>Create Design</strong> to generate an architecture and begin simulation.
        </div>
      ) : view === 'review' ? (
        <DesignReviewPanel design={design} onAccept={acceptDesign} onChangeRequest={requestChange} />
      ) : (
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Canvas */}
          <div style={{ flex: 1, position: 'relative' }}>
            <ReactFlow
              nodes={nodes} edges={edges}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes} edgeTypes={edgeTypes}
              fitView
              onNodeClick={(_, node) => setSelectedNode(node.id)}
              nodesDraggable={false}
            >
              <Background color="#2a2d35" gap={24} />
              <Controls />
              <MiniMap nodeStrokeWidth={2} pannable zoomable style={{ background: '#22252d' }} />
            </ReactFlow>
            {/* Legend */}
            <div className="pulse-legend">
              <div style={{ fontWeight: 600, marginBottom: 4, color: '#b0b4c0' }}>Flow</div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {[{l:'Request',c:'#3b82f6'},{l:'Data',c:'#06b6d4'},{l:'Auth',c:'#8b5cf6'},{l:'Approval',c:'#a855f7'},{l:'Response',c:'#10b981'},{l:'Retry',c:'#eab308'}].map(t => (
                  <span key={t.l} className="pulse-legend__item">
                    <span className="pulse-legend__swatch" style={{ background: t.c }} />{t.l}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: 6, fontWeight: 600, color: '#b0b4c0' }}>Status</div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {[{l:'Pass',c:'#22c55e'},{l:'Active',c:'#3b82f6'},{l:'Waiting',c:'#a855f7'},{l:'Degraded',c:'#f97316'},{l:'Blocked',c:'#ef4444'},{l:'Not Reached',c:'#5c6072'}].map(t => (
                  <span key={t.l} className="pulse-legend__item">
                    <span className="pulse-legend__swatch" style={{ background: t.c }} />{t.l}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: 6, fontSize: 9, color: '#5c6072' }}>
                All values shown are simulated — not live telemetry
              </div>
            </div>
          </div>

          {/* Right sidebar */}
          <div className="pulse-sidebar" style={{ width: 280 }}>
            <FlowScenarioSelector scenarios={scenarioList} current={scenario}
              onSelect={(s) => runSim(s as ScenarioId)} disabled={loading} />

            <div style={{ display: 'flex', gap: 4, marginTop: 10, marginBottom: 8 }}>
              <button onClick={() => { setPlaying(!playing); if (playbackMs < 0) setPlaybackMs(0); }}
                className={`pulse-btn pulse-btn--sm ${playing ? 'pulse-btn--warning' : 'pulse-btn--success'}`}>
                {playing ? '⏸ Pause' : '▶ Play'}
              </button>
              <button onClick={() => { setPlaying(false); setPlaybackMs(-1); events.length > 0 && applyState(simResult?.finalState!); }}
                className="pulse-btn pulse-btn--sm pulse-btn--ghost">↺ Reset</button>
              <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="pulse-select">
                <option value={0.5}>0.5x</option><option value={1}>1x</option>
                <option value={2}>2x</option><option value={4}>4x</option>
              </select>
            </div>

            {simResult && (
              <div style={{ fontSize: 10, color: '#5c6072', marginBottom: 8 }}>
                {simResult.source} | {simResult.durationMs}ms | {events.length} events
              </div>
            )}

            {simResult?.bottlenecks && simResult.bottlenecks.length > 0 && (
              <BottleneckPanel bottlenecks={simResult.bottlenecks} />
            )}

            {events.length > 0 && (
              <FlowTimeline events={events} playbackMs={playbackMs}
                onSeek={(ms) => { setPlaybackMs(ms); setPlaying(false); }} />
            )}

            {selectedNode && flow && (
              <FlowDetailsPanel nodeId={selectedNode} flow={flow}
                state={(nodes.find((n) => n.id === selectedNode)?.data as Record<string, any>)?.state}
                bottleneck={simResult?.bottlenecks?.find((b) => b.nodeId === selectedNode)} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
