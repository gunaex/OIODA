import React from 'react';
import type { ScenarioId } from '../model/flowTypes';

interface Props {
  scenarios: ScenarioId[];
  current: ScenarioId;
  onSelect: (s: ScenarioId) => void;
  disabled: boolean;
}

const SCENARIO_DESC: Record<string, string> = {
  HAPPY_PATH: 'All nodes pass',
  AUTH_FAILURE: 'Credential validation fails',
  FIREWALL_BLOCK: 'Firewall blocks request',
  DATABASE_SLOW: 'Database bottleneck',
  API_TIMEOUT: 'API gateway timeout',
  APPROVAL_WAIT: 'Approval gate pause',
  RETRY_RECOVERY: 'Retry after transient failure',
};

export default function FlowScenarioSelector({ scenarios, current, onSelect, disabled }: Props) {
  return (
    <div>
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Scenario</div>
      {scenarios.map((s) => (
        <button key={s} onClick={() => onSelect(s)} disabled={disabled}
          style={{
            display: 'block', width: '100%', textAlign: 'left', padding: '4px 8px',
            marginBottom: 2, border: '1px solid #e5e7eb', borderRadius: 4,
            background: current === s ? '#3b82f6' : '#fff',
            color: current === s ? '#fff' : '#374151',
            cursor: 'pointer', fontSize: 11,
          }}>
          <div style={{ fontWeight: 600 }}>{s.replace(/_/g, ' ')}</div>
          <div style={{ fontSize: 9, opacity: 0.7 }}>{SCENARIO_DESC[s]}</div>
        </button>
      ))}
    </div>
  );
}
