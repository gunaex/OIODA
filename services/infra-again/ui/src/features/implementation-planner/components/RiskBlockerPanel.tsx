import React from 'react';
import type { Risk, Blocker } from '../model/implementationTypes';

interface Props {
  risks: Risk[];
  blockers: Blocker[];
}

export default function RiskBlockerPanel({ risks, blockers }: Props) {
  const highBlockers = blockers.filter(b => b.severity === 'HIGH');
  const highRisks = risks.filter(r => r.severity === 'HIGH');

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>🚨 Risks & Blockers</h3>

      {blockers.length === 0 && risks.length === 0 && (
        <div style={{ color: '#22c55e', fontSize: 13 }}>✅ No blockers or risks identified.</div>
      )}

      {highBlockers.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#ef4444', marginBottom: 4 }}>
            🔴 HIGH Blockers ({highBlockers.length})
          </div>
          {highBlockers.map(b => (
            <div key={b.blockerId} style={{ padding: '6px 10px', borderLeft: '3px solid #ef4444', background: '#fef2f2', borderRadius: '0 6px 6px 0', marginBottom: 4, fontSize: 12 }}>
              {b.description} → {b.resolutionRequired}
            </div>
          ))}
        </div>
      )}

      {highRisks.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#f59e0b', marginBottom: 4 }}>
            🟡 HIGH Risks ({highRisks.length})
          </div>
          {highRisks.map(r => (
            <div key={r.riskId} style={{ padding: '6px 10px', borderLeft: '3px solid #f59e0b', background: '#fffbeb', borderRadius: '0 6px 6px 0', marginBottom: 4, fontSize: 12 }}>
              {r.title}: {r.description} {r.mitigation && <span style={{ color: '#22c55e' }}>→ {r.mitigation}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
