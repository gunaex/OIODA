import React from 'react';
import type { WorkPackage, Milestone } from '../model/implementationTypes';
import type { ScheduleMode } from '../model/implementationTypes';

interface Props {
  workPackages: WorkPackage[];
  milestones: Milestone[];
  criticalPath: string[];
  mode: ScheduleMode;
}

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

export default function ImplementationTimeline({ workPackages, milestones, criticalPath, mode }: Props) {
  const sortedPkgs = [...workPackages].sort((a, b) => {
    const aIdx = criticalPath.indexOf(a.packageId);
    const bIdx = criticalPath.indexOf(b.packageId);
    if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
    if (aIdx !== -1) return -1;
    if (bIdx !== -1) return 1;
    return 0;
  });

  const totalEffort = workPackages.reduce((s, w) => s + (w.estimatedEffort?.effortValue || 0), 0);
  const durationLabel = mode === 'FIT'
    ? `~${Math.ceil(totalEffort / 2)} days (2-person team)`
    : `~${totalEffort} person-days (ESTIMATED, DURATION_INCOMPLETE)`;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>📅 Timeline</h3>
        <span style={{ fontSize: 12, color: '#6b7280', fontStyle: 'italic' }}>{durationLabel}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {sortedPkgs.map(wp => {
          const isCritical = criticalPath.includes(wp.packageId);
          const color = TYPE_COLORS[wp.packageType] || '#6b7280';
          const barWidth = Math.max(8, (wp.estimatedEffort?.effortValue || 0.5) * 40);

          return (
            <div key={wp.packageId} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 140, textAlign: 'right', fontSize: 12, fontWeight: isCritical ? 700 : 400, color: isCritical ? '#ef4444' : '#374151' }}>
                {wp.title}
              </div>
              <div style={{
                height: 24,
                width: barWidth,
                background: `linear-gradient(90deg, ${color}, ${color}88)`,
                borderRadius: 4,
                border: isCritical ? '2px solid #ef4444' : '1px solid ' + color + '40',
                position: 'relative',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontSize: 10, color: '#fff', fontWeight: 600, textShadow: '0 0 3px rgba(0,0,0,0.3)' }}>
                  {wp.estimatedEffort?.effortValue}d
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {milestones.map(m => (
          <div key={m.milestoneId} style={{
            padding: '4px 10px',
            borderRadius: 12,
            background: m.completed ? '#dcfce7' : '#f3f4f6',
            border: `1px solid ${m.completed ? '#22c55e' : '#e5e7eb'}`,
            fontSize: 11,
            color: m.completed ? '#166534' : '#6b7280',
            textDecoration: m.completed ? 'none' : 'line-through',
          }}>
            {m.completed ? '✅' : '⏳'} {m.name}
          </div>
        ))}
      </div>
    </div>
  );
}

interface ScheduleModeToggleProps {
  mode: ScheduleMode;
  onChange: (mode: ScheduleMode) => void;
}

export function ScheduleModeToggle({ mode, onChange }: ScheduleModeToggleProps) {
  return (
    <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
      {(['RELAXED', 'FIT'] as ScheduleMode[]).map(m => (
        <button key={m} onClick={() => onChange(m)}
          style={{
            padding: '6px 16px',
            borderRadius: 20,
            border: mode === m ? '2px solid #3b82f6' : '1px solid #d1d5db',
            background: mode === m ? '#3b82f6' : '#fff',
            color: mode === m ? '#fff' : '#6b7280',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 600,
          }}>
          {m}
        </button>
      ))}
    </div>
  );
}
