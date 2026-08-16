import React from 'react';
import type { Gate, Risk, Blocker } from '../model/implementationTypes';

const GATE_COLORS: Record<string, string> = {
  PASS: '#22c55e',
  PENDING: '#f59e0b',
  FAIL: '#ef4444',
};

interface Props {
  readiness: string;
  gates: Gate[];
  blockers: Blocker[];
  risks: Risk[];
  openQuestions: string[];
}

export default function ReadinessMatrix({ readiness, gates, blockers, risks, openQuestions }: Props) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>
        ✅ Readiness: <span style={{ color: readiness === 'PARTIALLY_READY' ? '#f59e0b' : '#22c55e' }}>{readiness}</span>
      </h3>

      {/* Gates */}
      <div style={{ marginBottom: 12 }}>
        <h4 style={{ fontSize: 13, margin: '0 0 6px', color: '#6b7280' }}>Gates</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {gates.map(g => (
            <div key={g.gateId} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: '#f9fafb', borderRadius: 6, fontSize: 13 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: GATE_COLORS[g.state] || '#6b7280', display: 'inline-block' }} />
              <strong>{g.name}</strong>
              <span style={{ color: '#9ca3af' }}>{g.description}</span>
              <span style={{ marginLeft: 'auto', fontSize: 11, padding: '1px 8px', borderRadius: 8, background: (GATE_COLORS[g.state] || '#6b7280') + '20', color: GATE_COLORS[g.state], fontWeight: 600 }}>
                {g.state}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Blockers */}
      {blockers.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h4 style={{ fontSize: 13, margin: '0 0 6px', color: '#ef4444' }}>🚫 Blockers ({blockers.length})</h4>
          {blockers.map(b => (
            <div key={b.blockerId} style={{ border: '1px solid #fecaca', borderRadius: 8, padding: 10, marginBottom: 6, background: '#fef2f2', fontSize: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{b.description}</strong>
                <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 8, background: b.severity === 'HIGH' ? '#ef444420' : '#f59e0b20', color: b.severity === 'HIGH' ? '#ef4444' : '#f59e0b' }}>
                  {b.severity}
                </span>
              </div>
              <div style={{ color: '#6b7280', marginTop: 4 }}>Resolution: {b.resolutionRequired}</div>
            </div>
          ))}
        </div>
      )}

      {/* Risks */}
      {risks.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h4 style={{ fontSize: 13, margin: '0 0 6px', color: '#f59e0b' }}>⚠️ Risks ({risks.length})</h4>
          {risks.map(r => (
            <div key={r.riskId} style={{ border: '1px solid #fde68a', borderRadius: 8, padding: 10, marginBottom: 6, background: '#fffbeb', fontSize: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{r.title}</strong>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span style={{ fontSize: 11, color: '#6b7280' }}>P:{r.probability.toFixed(1)}</span>
                  <span style={{ fontSize: 11, color: '#6b7280' }}>I:{r.impact.toFixed(1)}</span>
                </div>
              </div>
              <div style={{ color: '#6b7280', marginTop: 2 }}>{r.description}</div>
            </div>
          ))}
        </div>
      )}

      {/* Open questions */}
      {openQuestions.length > 0 && (
        <div>
          <h4 style={{ fontSize: 13, margin: '0 0 6px', color: '#6b7280' }}>❓ Open Questions</h4>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: '#6b7280' }}>
            {openQuestions.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
