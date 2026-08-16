import React from 'react';
import type { FlowDefinition, FlowNodeState, FlowBottleneck } from '../model/flowTypes';
import { STATE_LABELS, STATE_COLORS } from '../model/flowTypes';

interface Props {
  nodeId: string;
  flow: FlowDefinition;
  state?: FlowNodeState;
  bottleneck?: FlowBottleneck;
}

export default function FlowDetailsPanel({ nodeId, flow, state, bottleneck }: Props) {
  const node = flow.nodes.find((n) => n.nodeId === nodeId);
  if (!node) return null;

  const color = state ? STATE_COLORS[state] : '#6b7280';

  return (
    <div style={{ marginTop: 12, padding: 10, background: '#fff', borderRadius: 6, border: '1px solid #e5e7eb', fontSize: 11 }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{node.label}</div>
      <div style={{ color: '#6b7280', marginBottom: 4 }}>{node.description}</div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
        <span style={{ padding: '1px 6px', borderRadius: 3, background: `${color}20`, color, fontWeight: 600, fontSize: 10 }}>
          {state ? STATE_LABELS[state] : '— Idle'}
        </span>
        <span style={{ color: '#9ca3af', fontSize: 10 }}>{node.category}</span>
        {node.provider && <span style={{ color: '#9ca3af', fontSize: 10 }}>{node.provider}</span>}
      </div>

      {bottleneck && (
        <div style={{ marginTop: 6, padding: 6, background: '#fff7ed', borderRadius: 4, border: '1px solid #fed7aa' }}>
          <div style={{ fontWeight: 600, color: '#c2410c' }}>Bottleneck</div>
          <div style={{ fontSize: 10, color: '#9a3412' }}>{bottleneck.explanation}</div>
          <div style={{ fontSize: 10, marginTop: 2 }}>Score: {bottleneck.score} | Severity: {bottleneck.severity}</div>
        </div>
      )}

      <div style={{ marginTop: 6 }}>
        <div style={{ fontWeight: 600, fontSize: 10, color: '#6b7280' }}>WHAT IS THIS?</div>
        <div style={{ fontSize: 10, color: '#374151' }}>{node.description || `${node.label} processes incoming ${node.category.toLowerCase()} traffic.`}</div>
      </div>
      <div style={{ marginTop: 4 }}>
        <div style={{ fontWeight: 600, fontSize: 10, color: '#6b7280' }}>WHAT HAPPENS IF IT FAILS?</div>
        <div style={{ fontSize: 10, color: '#374151' }}>
          {node.category === 'SECURITY' ? 'Traffic is blocked. Downstream components become NOT_REACHED.' :
           node.category === 'DATABASE' ? 'Application becomes degraded or fails. Data operations stop.' :
           node.category === 'GATEWAY' ? 'All API traffic is blocked. Service becomes unavailable.' :
           'Downstream components cannot process requests.'}
        </div>
      </div>
      {node.provider && (
        <div style={{ marginTop: 4, fontSize: 10, color: '#9ca3af' }}>
          REAL IMPLEMENTATION: NOT STARTED (no cloud resources created)
        </div>
      )}
    </div>
  );
}
