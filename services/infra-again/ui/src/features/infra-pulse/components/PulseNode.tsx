import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { FlowNodeState, NodeCategory } from '../model/flowTypes';

interface PulseNodeData {
  label: string;
  state: FlowNodeState;
  category: NodeCategory;
  provider?: string;
  description?: string;
  latencyMs?: number;
}

const CATEGORY_ICONS: Record<string, string> = {
  USER: '👤', IDENTITY: '🔑', SECURITY: '🛡', NETWORK: '🌐',
  GATEWAY: '🚪', APPLICATION: '⚙', SERVICE: '🔧', WORKFLOW: '📋',
  DATABASE: '🗄', STORAGE: '💾', QUEUE: '📬', CACHE: '⚡',
  OBSERVABILITY: '📊', EXTERNAL: '🔗', APPROVAL: '✅',
  PROVIDER: '☁', PLATFORM: '🖥',
};

function PulseNode({ data, selected }: NodeProps) {
  const d = data as unknown as PulseNodeData;
  const stateClass = `pulse-node--${d.state.toLowerCase()}`;
  const isActive = d.state === 'ACTIVE' || d.state === 'RETRYING';
  const isDegraded = d.state === 'DEGRADED';
  const icon = CATEGORY_ICONS[d.category] || '⬡';

  return (
    <div className={`pulse-node ${stateClass}`} style={{ boxShadow: selected ? '0 0 0 2px #60a5fa, 0 2px 8px rgba(0,0,0,0.4)' : undefined }}>
      <Handle type="target" position={Position.Left} style={{ background: 'var(--text-secondary)', border: 'none' }} />
      <div className="pulse-node__header">
        <span>{icon}</span>
        <span>{d.label}</span>
      </div>
      <div className="pulse-node__status">
        <span className={`pulse-node__status-dot ${isActive ? 'pulse-node__status-dot--active' : ''} ${isDegraded ? 'pulse-node__status-dot--degraded' : ''}`}
          style={{
            background: isActive ? '#3b82f6' : isDegraded ? '#f97316' :
              d.state === 'PASS' || d.state === 'COMPLETED' ? '#22c55e' :
              d.state === 'BLOCKED' || d.state === 'FAILED' ? '#ef4444' :
              d.state === 'WAITING' ? '#a855f7' : '#5c6072',
          }} />
        <span>{d.state.replace(/_/g, ' ')}</span>
      </div>
      {d.latencyMs != null && (
        <div className="pulse-node__metric">{d.latencyMs} ms</div>
      )}
      {d.provider && (
        <div className="pulse-node__provider">{d.provider}</div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: 'var(--text-secondary)', border: 'none' }} />
    </div>
  );
}

export default memo(PulseNode);
