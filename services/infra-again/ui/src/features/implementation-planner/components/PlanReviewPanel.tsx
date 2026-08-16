import React, { useState } from 'react';
import type { ImplementationPlan } from '../model/implementationTypes';

interface Props {
  plan: ImplementationPlan;
  onApprove: (approvedBy: string) => void;
  onRequestChange: (comment: string, affectedPackage?: string, affectedTask?: string) => void;
  loading?: boolean;
}

export default function PlanReviewPanel({ plan, onApprove, onRequestChange, loading }: Props) {
  const [reviewer, setReviewer] = useState('qa');
  const [showConfirm, setShowConfirm] = useState(false);
  const [changeComment, setChangeComment] = useState('');
  const [changePkg, setChangePkg] = useState('');
  const [changeTask, setChangeTask] = useState('');
  const [showChangeForm, setShowChangeForm] = useState(false);

  const isApproved = plan.status === 'APPROVED_FOR_EXECUTION';
  const isChangeRequested = plan.status === 'CHANGE_REQUESTED';

  if (isApproved) {
    return (
      <div style={{ border: '2px solid #22c55e', borderRadius: 12, padding: 20, marginBottom: 16, background: '#f0fdf4' }}>
        <h3 style={{ margin: '0 0 8px', color: '#166534' }}>✅ Plan Approved for Execution</h3>
        <div style={{ fontSize: 13, color: '#166534', display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
          <strong>Approved by:</strong><span>{plan.approvedBy}</span>
          <strong>Approved at:</strong><span>{plan.approvedAt}</span>
          <strong>Plan checksum:</strong><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{plan.planChecksum}</span>
          <strong>Design revision:</strong><span>{plan.designRevision}</span>
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: '#6b7280', fontStyle: 'italic' }}>
          No infrastructure will be created by this action.
        </div>
      </div>
    );
  }

  if (isChangeRequested) {
    return (
      <div style={{ border: '2px solid #f59e0b', borderRadius: 12, padding: 20, marginBottom: 16, background: '#fffbeb' }}>
        <h3 style={{ margin: '0 0 8px', color: '#92400e' }}>🔄 Change Requested</h3>
        <div style={{ fontSize: 13, color: '#92400e' }}>
          Material changes will create a new plan revision. The current approved revision is preserved.
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>📝 Plan Review & Approval</h3>

      {showChangeForm ? (
        <div style={{ border: '1px solid #f59e0b', borderRadius: 12, padding: 16, marginBottom: 12, background: '#fffbeb' }}>
          <h4 style={{ margin: '0 0 8px', fontSize: 14 }}>Request Change</h4>
          <textarea value={changeComment} onChange={e => setChangeComment(e.target.value)}
            placeholder="Describe the change needed..."
            style={{ width: '100%', minHeight: 60, padding: 8, border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, marginBottom: 8 }}
          />
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input value={changePkg} onChange={e => setChangePkg(e.target.value)}
              placeholder="Affected package (optional)" style={{ flex: 1, padding: 6, border: '1px solid #d1d5db', borderRadius: 6, fontSize: 12 }} />
            <input value={changeTask} onChange={e => setChangeTask(e.target.value)}
              placeholder="Affected task (optional)" style={{ flex: 1, padding: 6, border: '1px solid #d1d5db', borderRadius: 6, fontSize: 12 }} />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => { onRequestChange(changeComment, changePkg || undefined, changeTask || undefined); setShowChangeForm(false); }}
              disabled={!changeComment.trim() || loading}
              style={{ padding: '8px 16px', background: '#f59e0b', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>
              Submit Change Request
            </button>
            <button onClick={() => setShowChangeForm(false)}
              style={{ padding: '8px 16px', background: '#e5e7eb', color: '#374151', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <button onClick={() => setShowConfirm(true)}
            disabled={loading}
            style={{ padding: '8px 20px', background: '#22c55e', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>
            ✅ Approve Implementation Plan
          </button>
          <button onClick={() => setShowChangeForm(true)}
            disabled={loading}
            style={{ padding: '8px 20px', background: '#f59e0b', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>
            🔄 Request Change
          </button>
        </div>
      )}

      {showConfirm && (
        <div style={{ border: '2px solid #22c55e', borderRadius: 12, padding: 16, background: '#f0fdf4' }}>
          <h4 style={{ margin: '0 0 8px', color: '#166534' }}>⚠️ Confirm Approval</h4>
          <p style={{ fontSize: 13, color: '#166534', marginBottom: 8 }}>
            You are approving the implementation plan only.<br />
            <strong>No infrastructure will be created by this action.</strong>
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input value={reviewer} onChange={e => setReviewer(e.target.value)}
              placeholder="Reviewer name" style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, width: 200 }} />
            <button onClick={() => { onApprove(reviewer); setShowConfirm(false); }}
              disabled={!reviewer.trim() || loading}
              style={{ padding: '8px 20px', background: '#166534', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>
              Confirm Approval
            </button>
            <button onClick={() => setShowConfirm(false)}
              style={{ padding: '8px 16px', background: '#e5e7eb', color: '#374151', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
