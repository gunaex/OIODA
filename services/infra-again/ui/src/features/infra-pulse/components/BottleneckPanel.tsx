import React from 'react';
import type { FlowBottleneck } from '../model/flowTypes';

interface Props {
  bottlenecks: FlowBottleneck[];
}

export default function BottleneckPanel({ bottlenecks }: Props) {
  if (bottlenecks.length === 0) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4, color: '#c2410c' }}>Bottlenecks</div>
      {bottlenecks.map((b) => (
        <div key={b.nodeId} style={{
          padding: 8, background: '#fff7ed', borderRadius: 6,
          border: '1px solid #fed7aa', marginBottom: 6, fontSize: 11,
        }}>
          <div style={{ fontWeight: 600, color: '#9a3412' }}>{b.nodeId}</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
            <span style={{ fontWeight: 700, fontSize: 16, color: '#ea580c' }}>{b.score}</span>
            <span style={{ color: '#9a3412' }}>{b.severity}</span>
          </div>
          <div style={{ color: '#9a3412', marginTop: 2 }}>{b.explanation}</div>
          {b.factors.map((f, i) => (
            <div key={i} style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>
              {f.type}: {f.value}{f.unit || ''} [{f.source}]
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
