import React from 'react';
import type { ImplementationPlan, PlanSummary } from '../model/implementationTypes';
import { deriveSummary } from '../model/implementationMapper';

const STATUS_COLORS: Record<string, string> = {
  REVIEW_READY: '#3b82f6',
  APPROVED_FOR_EXECUTION: '#22c55e',
  CHANGE_REQUESTED: '#f59e0b',
  CHANGED_AFTER_APPROVAL: '#ef4444',
  PARTIALLY_READY: '#f59e0b',
  READY_FOR_LOCAL_IMPLEMENTATION: '#22c55e',
};

function StatusBadge({ status, style }: { status: string; style?: React.CSSProperties }) {
  const color = STATUS_COLORS[status] || '#6b7280';
  return <span style={{ display: 'inline-block', background: color, color: '#fff', padding: '2px 10px', borderRadius: 14, fontSize: 12, fontWeight: 600, ...style }}>{status}</span>;
}

interface Props {
  plan: ImplementationPlan;
}

export default function PlanSummary({ plan }: Props) {
  const s: PlanSummary = deriveSummary(plan);

  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>📋 Implementation Plan</h2>
        <StatusBadge status={plan.status} />
      </div>

      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 12 }}>
        {plan.summary}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
        <Stat label="Plan ID" value={s.planId} mono />
        <Stat label="Design" value={`${s.designId} (rev ${s.designRevision})`} />
        <Stat label="Readiness" value={<StatusBadge status={s.readiness} style={{ fontSize: 11 }} />} />
        <Stat label="Packages" value={String(s.packageCount)} />
        <Stat label="Tasks" value={String(s.taskCount)} />
        <Stat label="Dependencies" value={String(s.dependencyCount)} />
        <Stat label="Blockers" value={String(s.blockerCount)} accent={s.blockerCount > 0} />
        <Stat label="Risks" value={String(s.riskCount)} accent={s.riskCount > 0} />
        <Stat label="Checksum" value={plan.planChecksum.slice(0, 12) + '…'} mono />
      </div>

      {plan.approvedBy && (
        <div style={{ marginTop: 10, fontSize: 12, color: '#22c55e', fontStyle: 'italic' }}>
          Approved by {plan.approvedBy} at {plan.approvedAt}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, mono, accent }: { label: string; value: React.ReactNode; mono?: boolean; accent?: boolean }) {
  return (
    <div style={{ padding: '8px 10px', background: '#f9fafb', borderRadius: 8 }}>
      <div style={{ fontSize: 11, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, fontFamily: mono ? 'monospace' : undefined, color: accent ? '#ef4444' : '#111827', marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}
