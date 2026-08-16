import React from 'react';
import type { FlowEvent } from '../model/flowTypes';

interface Props {
  events: FlowEvent[];
  playbackMs: number;
  onSeek: (ms: number) => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  INFO: '#6b7280', WARNING: '#f59e0b', HIGH: '#f97316', CRITICAL: '#ef4444',
};

export default function FlowTimeline({ events, playbackMs, onSeek }: Props) {
  const maxMs = events.length > 0 ? events[events.length - 1].timestampMs : 1;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Timeline</div>
      <input type="range" min={0} max={maxMs}
        value={playbackMs >= 0 ? playbackMs : maxMs}
        onChange={(e) => onSeek(Number(e.target.value))}
        style={{ width: '100%', accentColor: '#3b82f6' }} />
      <div style={{ fontSize: 9, color: '#6b7280', display: 'flex', justifyContent: 'space-between' }}>
        <span>0ms</span><span>{playbackMs >= 0 ? `${playbackMs}ms` : `${maxMs}ms (end)`}</span>
      </div>
      <div style={{ maxHeight: 150, overflow: 'auto', marginTop: 4 }}>
        {events.slice(0, 30).map((e) => (
          <div key={e.eventId}
            onClick={() => onSeek(e.timestampMs)}
            style={{
              padding: '2px 6px', fontSize: 10, cursor: 'pointer', borderRadius: 2,
              background: e.timestampMs <= (playbackMs >= 0 ? playbackMs : Infinity) ? '#eff6ff' : 'transparent',
              borderLeft: `3px solid ${SEVERITY_COLORS[e.severity] || '#6b7280'}`,
              marginBottom: 1,
            }}>
            <span style={{ color: '#9ca3af', marginRight: 4 }}>{e.timestampMs}ms</span>
            <span>{e.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
