import React from 'react';
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@xyflow/react';
import type { FlowEdgeState, FlowType } from '../model/flowTypes';
import { STATE_COLORS, FLOW_TYPE_COLORS } from '../model/flowTypes';

interface PulseEdgeData {
  state: FlowEdgeState;
  flowType: FlowType;
  label?: string;
}

export default function PulseEdge(props: EdgeProps) {
  const d = (props.data || {}) as unknown as PulseEdgeData;
  const state = d.state || 'IDLE';
  const flowType = d.flowType || 'REQUEST';
  const color = STATE_COLORS[state] || FLOW_TYPE_COLORS[flowType] || '#3b82f6';
  const isFlowing = state === 'FLOWING' || state === 'COMPLETED';
  const isBlocked = state === 'BLOCKED' || state === 'FAILED';
  const isSlow = state === 'SLOW' || state === 'CONGESTED';

  const [edgePath] = getSmoothStepPath({
    sourceX: props.sourceX, sourceY: props.sourceY,
    targetX: props.targetX, targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
    borderRadius: 8,
  });

  return (
    <>
      <BaseEdge
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth: isFlowing ? 2.5 : 1.5,
          strokeDasharray: isBlocked ? '6 4' : isFlowing ? 'none' : '4 4',
          opacity: state === 'IDLE' ? 0.3 : 1,
          transition: 'stroke 0.3s, stroke-width 0.3s, opacity 0.3s',
        }}
        markerEnd={isBlocked ? undefined : `url(#arrow-${color.replace('#', '')})`}
      />
      {/* Animated pulse for flowing edges */}
      {isFlowing && (
        <circle
          r={4}
          fill={color}
          opacity={0.8}
          style={{ filter: `drop-shadow(0 0 3px ${color})` }}
        >
          <animateMotion
            dur={isSlow ? '2.5s' : '1.2s'}
            repeatCount="indefinite"
            path={edgePath}
          />
        </circle>
      )}
      {/* Blocked barrier */}
      {isBlocked && (
        <circle r={6} fill="#ef4444" opacity={0.9}>
          <animateMotion
            dur="0.01s"
            fill="freeze"
            path={edgePath}
            keyPoints="0.5;0.5"
            keyTimes="0;1"
          />
        </circle>
      )}
      {/* Edge label */}
      {d.label && (
        <text>
          <textPath
            href={`#${props.id}-labelpath`}
            startOffset="50%"
            textAnchor="middle"
            style={{ fontSize: 9, fill: '#6b7280' }}
          >
            {d.label}
          </textPath>
        </text>
      )}
      <path
        id={`${props.id}-labelpath`}
        d={edgePath}
        fill="none"
        style={{ visibility: 'hidden' }}
      />
    </>
  );
}
