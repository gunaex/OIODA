import React from 'react';
import type { WorkPackage } from '../model/implementationTypes';

const TYPE_COLORS: Record<string, string> = {
  SECURITY: '#8b5cf6',
  APPLICATION: '#3b82f6',
  DATABASE: '#22c55e',
  STORAGE: '#f59e0b',
  INTEGRATION: '#06b6d4',
  TESTING: '#ec4899',
  DEPLOYMENT: '#ef4444',
  DOCUMENTATION: '#6b7280',
};

const TASK_STATUS_COLORS: Record<string, string> = {
  PLANNED: '#6b7280',
  IN_PROGRESS: '#3b82f6',
  COMPLETED: '#22c55e',
  BLOCKED: '#ef4444',
  FAILED: '#ef4444',
};

interface Props {
  packages: WorkPackage[];
  onSelect?: (pkg: WorkPackage) => void;
  selectedId?: string;
}

export default function WorkPackageList({ packages, onSelect, selectedId }: Props) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 12px 0', fontSize: 16 }}>📦 Work Packages ({packages.length})</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {packages.map(wp => (
          <div
            key={wp.packageId}
            onClick={() => onSelect?.(wp)}
            style={{
              border: `2px solid ${selectedId === wp.packageId ? TYPE_COLORS[wp.packageType] || '#6b7280' : '#e5e7eb'}`,
              borderLeft: `4px solid ${TYPE_COLORS[wp.packageType] || '#6b7280'}`,
              borderRadius: 8,
              padding: 12,
              cursor: onSelect ? 'pointer' : 'default',
              background: selectedId === wp.packageId ? '#f9fafb' : '#fff',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ fontSize: 14 }}>{wp.title}</strong>
                <span style={{ marginLeft: 8, fontSize: 11, color: '#6b7280', fontFamily: 'monospace' }}>{wp.packageId}</span>
              </div>
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: (TYPE_COLORS[wp.packageType] || '#6b7280') + '20', color: TYPE_COLORS[wp.packageType] || '#6b7280', fontWeight: 600 }}>
                {wp.packageType}
              </span>
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>
              {wp.tasks.length} tasks · {wp.estimatedEffort.effortValue} {wp.estimatedEffort.effortUnit}
              {wp.parallelGroup && <span> · {wp.parallelGroup}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function WorkPackageDetails({ wp }: { wp: WorkPackage }) {
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 18 }}>{wp.title}</h3>
        <span style={{ fontSize: 11, padding: '2px 10px', borderRadius: 10, background: (TYPE_COLORS[wp.packageType] || '#6b7280') + '20', color: TYPE_COLORS[wp.packageType] || '#6b7280', fontWeight: 600 }}>
          {wp.packageType}
        </span>
      </div>
      <p style={{ fontSize: 13, color: '#6b7280', margin: '0 0 12px' }}>{wp.description}</p>

      <h4 style={{ fontSize: 14, margin: '12px 0 8px' }}>Tasks ({wp.tasks.length})</h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {wp.tasks.map(t => (
          <div key={t.taskId} style={{ border: '1px solid #f3f4f6', borderRadius: 6, padding: 10, fontSize: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>{t.title}</strong>
              <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 8, background: (TASK_STATUS_COLORS[t.status] || '#6b7280') + '20', color: TASK_STATUS_COLORS[t.status] }}>
                {t.status}
              </span>
            </div>
            <div style={{ color: '#9ca3af', marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <span>⚡ {t.automation}</span>
              <span>🖥️ {t.executionMode}</span>
              <span>📏 {t.estimatedEffort.effortValue} {t.estimatedEffort.effortUnit}</span>
              <span>📦 {t.deliveryStage}</span>
              {t.localValidatable && <span style={{ color: '#22c55e' }}>✓ local</span>}
            </div>
            {t.acceptanceCriteria.length > 0 && (
              <div style={{ marginTop: 6, padding: '6px 8px', background: '#f9fafb', borderRadius: 4, fontSize: 11 }}>
                <strong>Acceptance:</strong>
                <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
                  {t.acceptanceCriteria.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
            {t.derivedFrom.length > 0 && (
              <div style={{ marginTop: 4, fontSize: 10, color: '#9ca3af' }}>
                derived: {t.derivedFrom.map(d => `${d.type}:${d.id}`).join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
