import React from 'react';
import type { WorkPackage } from '../model/implementationTypes';

interface Props {
  criticalPath: string[];
  workPackages: WorkPackage[];
}

export default function CriticalPathPanel({ criticalPath, workPackages }: Props) {
  const pkgMap = new Map(workPackages.map(w => [w.packageId, w]));
  const totalEffort = criticalPath.reduce((sum, id) => {
    const pkg = pkgMap.get(id);
    return sum + (pkg?.estimatedEffort?.effortValue || 0);
  }, 0);

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>⏱️ Critical Path</h3>
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        {criticalPath.map((id, i) => {
          const pkg = pkgMap.get(id);
          return (
            <React.Fragment key={id}>
              {i > 0 && <span style={{ color: '#ef4444', fontWeight: 700, fontSize: 18 }}>→</span>}
              <div style={{
                border: '1px solid #ef4444',
                borderRadius: 8,
                padding: '8px 12px',
                background: '#fef2f2',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{pkg?.title || id}</div>
                <div style={{ fontSize: 11, color: '#9ca3af', fontFamily: 'monospace' }}>{id}</div>
                <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
                  {pkg?.estimatedEffort?.effortValue || '?'} {pkg?.estimatedEffort?.effortUnit || ''}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>
        Estimated total: <strong>{totalEffort} person-days</strong> ({criticalPath.length} packages)
      </div>
    </div>
  );
}
