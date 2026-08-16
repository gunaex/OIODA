export type FlowNodeState =
  'IDLE' | 'NOT_REACHED' | 'ACTIVE' | 'WAITING' | 'PASS' |
  'DEGRADED' | 'BLOCKED' | 'FAILED' | 'RETRYING' | 'COMPLETED';
export type FlowEdgeState =
  'IDLE' | 'FLOWING' | 'SLOW' | 'CONGESTED' | 'WAITING' |
  'BLOCKED' | 'FAILED' | 'RETRYING' | 'COMPLETED';
export type FlowType =
  'REQUEST' | 'DATA' | 'AUTH' | 'CONTROL' | 'APPROVAL' |
  'OBSERVATION' | 'EVENT' | 'RESPONSE' | 'RETRY';
export type NodeCategory =
  'USER' | 'IDENTITY' | 'SECURITY' | 'NETWORK' | 'GATEWAY' |
  'APPLICATION' | 'SERVICE' | 'WORKFLOW' | 'DATABASE' | 'STORAGE' |
  'QUEUE' | 'CACHE' | 'OBSERVABILITY' | 'EXTERNAL' | 'APPROVAL' |
  'PROVIDER' | 'PLATFORM';
export type DesignStatus =
  'DRAFT' | 'GENERATED' | 'REVIEW_READY' | 'USER_REVIEW' |
  'CHANGE_REQUESTED' | 'ACCEPTED' | 'BASELINE_FROZEN' |
  'DESIGN_CHANGED_AFTER_ACCEPTANCE' | 'READY_FOR_IMPLEMENTATION';
export type ScenarioId =
  'HAPPY_PATH' | 'AUTH_FAILURE' | 'FIREWALL_BLOCK' | 'DATABASE_SLOW' |
  'API_TIMEOUT' | 'APPROVAL_WAIT' | 'RETRY_RECOVERY';

export interface FlowNode {
  nodeId: string; label: string; description: string;
  category: NodeCategory; provider: string; platform: string;
  state: FlowNodeState; position: { x: number; y: number };
  groupId: string; metadata: Record<string, unknown>;
}
export interface FlowEdge {
  edgeId: string; sourceId: string; targetId: string;
  flowType: FlowType; state: FlowEdgeState; label: string;
  metadata: Record<string, unknown>;
}
export interface FlowMetric {
  name: string; value: number; unit: string;
  source: 'SIMULATED' | 'ESTIMATED' | 'OBSERVED' | 'IMPORTED';
  confidence: number;
}
export interface FlowEvent {
  eventId: string; flowId: string; timestampMs: number;
  eventType: string; nodeId: string; edgeId: string;
  severity: string; source: string; message: string;
  metadata: Record<string, unknown>;
}
export interface FlowBottleneck {
  nodeId: string; score: number | null; severity: string;
  factors: Array<{ type: string; value: number; source: string; unit?: string }>;
  explanation: string;
}
export interface FlowDefinition {
  flowId: string; name: string; flowType: FlowType;
  architectureGraphId: string; entryNodeId: string;
  nodes: FlowNode[]; edges: FlowEdge[];
  groups: Array<{ groupId: string; label: string; type: string }>;
  scenario: string; simulationSeed: number;
  metadata: Record<string, unknown>;
}
export interface FlowPlaybackState {
  flowId: string; timestampMs: number;
  nodeStates: Record<string, FlowNodeState>;
  edgeStates: Record<string, FlowEdgeState>;
  activePath: string[];
  bottlenecks: FlowBottleneck[];
  currentEvent: FlowEvent | null;
}
export interface Design {
  designId: string; revision: number; status: DesignStatus;
  requirementsChecksum: string; architectureChecksum: string;
  flowChecksum: string; acceptedAt: string; acceptedBy: string;
  changeRequests: Array<{ comment: string; nodeId: string; severity: string; timestamp: string }>;
  createdAt: string; metadata: Record<string, unknown>;
}
export interface SimulationResult {
  simulationId: string; designId: string; flowId: string;
  scenario: string; source: string; durationMs: number;
  events: FlowEvent[]; bottlenecks: FlowBottleneck[];
  finalState: FlowPlaybackState;
}

export const STATE_COLORS: Record<string, string> = {
  IDLE: '#6b7280', NOT_REACHED: '#6b7280', ACTIVE: '#3b82f6',
  WAITING: '#a855f7', PASS: '#22c55e', DEGRADED: '#f97316',
  BLOCKED: '#ef4444', FAILED: '#ef4444', RETRYING: '#eab308',
  COMPLETED: '#22c55e',
};
export const FLOW_TYPE_COLORS: Record<string, string> = {
  REQUEST: '#3b82f6', DATA: '#06b6d4', AUTH: '#8b5cf6',
  CONTROL: '#6366f1', APPROVAL: '#a855f7', OBSERVATION: '#06b6d4',
  EVENT: '#f59e0b', RESPONSE: '#10b981', RETRY: '#eab308',
};
export const STATE_LABELS: Record<string, string> = {
  BLOCKED: '✕ Blocked', FAILED: '✕ Failed', PASS: '✓ Pass',
  ACTIVE: '▶ Active', WAITING: '⏳ Waiting', DEGRADED: '⚠ Degraded',
  RETRYING: '↻ Retrying', COMPLETED: '✓ Done', IDLE: '— Idle',
  NOT_REACHED: '— Not Reached',
};
