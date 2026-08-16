import React, { useState, useEffect } from 'react';
import type { PMHandoff, QAHandoff } from '../model/implementationTypes';
import { getPMHandoff, getQAHandoff } from '../model/implementationMapper';

interface Props {
  planId: string;
}

export default function HandoffPanel({ planId }: Props) {
  const [tab, setTab] = useState<'pm' | 'qa'>('pm');
  const [pm, setPm] = useState<PMHandoff | null>(null);
  const [qa, setQa] = useState<QAHandoff | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = async (type: 'pm' | 'qa') => {
    setLoading(true); setError('');
    try {
      if (type === 'pm') { const d = await getPMHandoff(planId); setPm(d); }
      else { const d = await getQAHandoff(planId); setQa(d); }
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (tab === 'pm' && !pm) load('pm');
    else if (tab === 'qa' && !qa) load('qa');
  }, [tab]);

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>📋 Handoff</h3>

      <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
        {(['pm', 'qa'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              padding: '6px 16px', border: tab === t ? '2px solid #3b82f6' : '1px solid #d1d5db',
              background: tab === t ? '#3b82f6' : '#fff', color: tab === t ? '#fff' : '#6b7280',
              borderRadius: 20, cursor: 'pointer', fontSize: 13, fontWeight: 600,
            }}>
            {t === 'pm' ? '👷 PM Handoff' : '🧪 QA Handoff'}
          </button>
        ))}
        <button onClick={() => {
          const data = tab === 'pm' ? pm : qa;
          if (data) {
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = `handoff-${tab}-${planId}.json`;
            a.click(); URL.revokeObjectURL(url);
          }
        }} style={{ marginLeft: 'auto', padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 12 }}>
          📥 Download JSON
        </button>
      </div>

      {loading && <div style={{ color: '#6b7280', fontSize: 13 }}>Loading...</div>}
      {error && <div style={{ color: '#ef4444', fontSize: 13 }}>{error}</div>}

      {tab === 'pm' && pm && (
        <div style={{ fontSize: 13 }}>
          <div style={{ marginBottom: 8 }}>
            <strong>Contract:</strong> {pm.contractVersion} · <strong>Plan:</strong> <span style={{ fontFamily: 'monospace' }}>{pm.planId}</span> · <strong>Packages:</strong> {pm.workPackages.length}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {pm.workPackages.map(wp => (
              <div key={wp.packageId} style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: 8 }}>
                <strong>{wp.title}</strong>
                <div style={{ color: '#6b7280' }}>{wp.packageType} · {wp.tasks.length} tasks · {wp.estimatedEffort?.effortValue}d</div>
              </div>
            ))}
          </div>
          {pm.totalEstimate && (
            <div style={{ marginTop: 8, color: '#6b7280' }}>
              Total: {pm.totalEstimate.effortValue} {pm.totalEstimate.effortUnit}
            </div>
          )}
        </div>
      )}

      {tab === 'qa' && qa && (
        <div style={{ fontSize: 13 }}>
          <div style={{ marginBottom: 8 }}>
            <strong>Contract:</strong> {qa.contractVersion} · <strong>Test Items:</strong> {qa.testItems.length}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {qa.testItems.map(ti => (
              <div key={ti.taskId} style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: 8 }}>
                <strong>{ti.title}</strong> <span style={{ fontSize: 11, color: '#6b7280' }}>{ti.riskLevel}</span>
                {ti.localValidatable && <span style={{ marginLeft: 6, fontSize: 11, color: '#22c55e' }}>✓ local</span>}
                <ul style={{ margin: '2px 0 0 16px', padding: 0, fontSize: 11, color: '#6b7280' }}>
                  {ti.acceptanceCriteria.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
                {ti.scenarioReferences.length > 0 && (
                  <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 2 }}>
                    Scenarios: {ti.scenarioReferences.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
