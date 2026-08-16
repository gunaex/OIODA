// Phase 8-9 Sandbox + Promotion types

export type ExecutionFidelity =
  | 'PLAN_ONLY'
  | 'SIMULATED'
  | 'LOCAL_RUNTIME'
  | 'LOCAL_PRIVATE_CLOUD'
  | 'SANDBOX'
  | 'CONTROLLED_REAL'
  | 'PRODUCTION';

export type SandboxExecutionState =
  | 'NOT_STARTED'
  | 'PREFLIGHT_RUNNING'
  | 'PREFLIGHT_PASSED'
  | 'PREFLIGHT_FAILED'
  | 'AWAITING_APPROVAL'
  | 'APPROVED'
  | 'CREDENTIAL_LEASED'
  | 'EXECUTING'
  | 'OBSERVING'
  | 'VALIDATING'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CLEANING_UP'
  | 'CLEANED_UP'
  | 'RECONCILIATION_REQUIRED';

export type ApprovalState = 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'REVOKED';

export type BlastRadiusLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN';

export type EnvironmentClass = 'LOCAL' | 'SANDBOX' | 'CONTROLLED_REAL' | 'PRODUCTION';

export interface SandboxAccount {
  accountId: string;
  provider: string;
  callerIdentity: { account: string; arn: string; userId: string };
  verified: boolean;
  verifiedAt: string;
}

export interface CostEstimate {
  estimatedMaximumCost: number;
  currency: string;
  costWindowHours: number;
  ceiling: number;
  source: string;
}

export interface CredentialLease {
  leaseId: string;
  source: string;
  principalArn: string;
  accountId: string;
  expiration: string;
  scope: string[];
}

export interface SandboxTarget {
  sandboxTargetId: string;
  provider: string;
  account: SandboxAccount;
  region: string;
  environment: string;
  resourceAllowlist: { services: string[]; maxResourceCount: number; blockedServices: string[] };
  costEstimate: CostEstimate;
  ttlHours: number;
  ownershipTags: Record<string, string>;
  cleanupPolicy: Record<string, boolean | Record<string, string>>;
  credentialLease: CredentialLease;
  production: boolean;
  createdAt: string;
}

export interface SandboxPreflightResult {
  preflightId: string;
  packageId: string;
  sandboxTargetId: string;
  checks: Record<string, boolean>;
  allPassed: boolean;
  failures: string[];
  checkedAt: string;
}

export interface SandboxApproval {
  approvalId: string;
  sandboxTargetId: string;
  executionPackageId: string;
  boundPlanChecksum: string;
  boundTargetChecksum: string;
  state: ApprovalState;
  approvedBy: string;
  approvedAt: string;
  expiresAt: string;
  warningMessage: string;
}

export interface SandboxExecution {
  executionId: string;
  sandboxTargetId: string;
  approvalId: string;
  packageId: string;
  state: SandboxExecutionState;
  target: SandboxTarget;
  preflight: SandboxPreflightResult;
  readyForRealExecution: boolean;
  note: string;
}

export interface EnvironmentTarget {
  environmentId: string;
  name: string;
  classification: EnvironmentClass;
  provider: string;
  accountId: string;
  region: string;
  allowedServices: string[];
  resourceScope: string;
  blastRadius: BlastRadiusLevel;
  costCeiling: number;
  maintenanceWindow: string;
  production: boolean;
}

// Fidelity display helpers
export const FIDELITY_COLORS: Record<ExecutionFidelity, string> = {
  PLAN_ONLY: '#6b7280',
  SIMULATED: '#8b5cf6',
  LOCAL_RUNTIME: '#3b82f6',
  LOCAL_PRIVATE_CLOUD: '#f59e0b',
  SANDBOX: '#ef4444',
  CONTROLLED_REAL: '#7f1d1d',
  PRODUCTION: '#991b1b',
};

export const FIDELITY_LABELS: Record<ExecutionFidelity, string> = {
  PLAN_ONLY: 'Plan Only',
  SIMULATED: 'Simulated',
  LOCAL_RUNTIME: 'Local Runtime',
  LOCAL_PRIVATE_CLOUD: 'Local Private Cloud',
  SANDBOX: '⚠ SANDBOX',
  CONTROLLED_REAL: '🚫 CONTROLLED REAL',
  PRODUCTION: '🚫 PRODUCTION',
};

export const FIDELITY_WARNINGS: Record<ExecutionFidelity, string> = {
  PLAN_ONLY: 'No infrastructure created.',
  SIMULATED: 'Local simulation only.',
  LOCAL_RUNTIME: 'Local runtime only.',
  LOCAL_PRIVATE_CLOUD: 'Requires explicit approval.',
  SANDBOX: '⚠ REAL CLOUD RESOURCES MAY BE CREATED',
  CONTROLLED_REAL: '🚫 NOT YET ENABLED',
  PRODUCTION: '🚫 NOT YET ENABLED',
};

export const STATE_COLORS: Record<string, string> = {
  NOT_STARTED: '#6b7280',
  PREFLIGHT_RUNNING: '#3b82f6',
  PREFLIGHT_PASSED: '#10b981',
  PREFLIGHT_FAILED: '#ef4444',
  AWAITING_APPROVAL: '#f59e0b',
  APPROVED: '#10b981',
  EXECUTING: '#3b82f6',
  OBSERVING: '#8b5cf6',
  VALIDATING: '#8b5cf6',
  VERIFYING: '#8b5cf6',
  COMPLETED: '#10b981',
  FAILED: '#ef4444',
  CLEANING_UP: '#f59e0b',
  CLEANED_UP: '#10b981',
  RECONCILIATION_REQUIRED: '#ef4444',
};
