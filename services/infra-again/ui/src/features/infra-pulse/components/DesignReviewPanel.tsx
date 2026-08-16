import React, { useState } from 'react';
import type { Design } from '../model/flowTypes';

interface Props {
  design: Design;
  onAccept: () => void;
  onChangeRequest: (comment: string) => void;
}

export default function DesignReviewPanel({ design, onAccept, onChangeRequest }: Props) {
  const [comment, setComment] = useState('');
  const isFrozen = design.status === 'BASELINE_FROZEN';

  return (
    <div style={{ padding: 20, maxWidth: 700, margin: '0 auto' }}>
      <h3>Design Review — {design.designId}</h3>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <InfoCard label="Status" value={design.status.replace(/_/g, ' ')} />
        <InfoCard label="Revision" value={String(design.revision)} />
        <InfoCard label="Requirements" value={design.requirementsChecksum || '—'} />
        <InfoCard label="Architecture" value={design.architectureChecksum || '—'} />
        <InfoCard label="Flow" value={design.flowChecksum || '—'} />
      </div>

      {design.changeRequests.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Change Requests</div>
          {design.changeRequests.map((cr, i) => (
            <div key={i} style={{
              padding: 6, background: '#fef3c7', borderRadius: 4, marginBottom: 4, fontSize: 12,
            }}>
              <div>{cr.comment}</div>
              <div style={{ color: '#6b7280', fontSize: 10 }}>
                {cr.nodeId && `Node: ${cr.nodeId} | `}{cr.severity} | {cr.timestamp}
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginBottom: 16 }}>
        <textarea value={comment} onChange={(e) => setComment(e.target.value)}
          placeholder="Describe requested change..."
          style={{ width: '100%', minHeight: 60, padding: 8, border: '1px solid #d1d5db', borderRadius: 4, fontSize: 12 }} />
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => { onChangeRequest(comment); setComment(''); }}
          disabled={!comment.trim()}
          style={{ padding: '8px 20px', background: comment.trim() ? '#f59e0b' : '#e5e7eb',
            color: comment.trim() ? '#fff' : '#9ca3af', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>
          Request Change
        </button>
        <button onClick={onAccept}
          disabled={isFrozen || design.status === 'CHANGE_REQUESTED'}
          style={{ padding: '8px 20px', background: isFrozen ? '#e5e7eb' : '#22c55e',
            color: isFrozen ? '#9ca3af' : '#fff', border: 'none', borderRadius: 6, cursor: isFrozen ? 'default' : 'pointer', fontWeight: 600 }}>
          {isFrozen ? '✓ Accepted' : 'Accept Design'}
        </button>
      </div>

      <div style={{ marginTop: 12, padding: 8, background: '#dbeafe', borderRadius: 4, fontSize: 11, color: '#1e40af' }}>
        Accepting this design freezes the proposed architecture and flow baseline.
        No infrastructure will be created by this action.
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: '6px 12px', background: '#f9fafb', borderRadius: 4, border: '1px solid #e5e7eb' }}>
      <div style={{ fontSize: 10, color: '#6b7280' }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace' }}>{value}</div>
    </div>
  );
}
