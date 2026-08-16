/* Implementation Planner — domain types (API-contract-aligned) */

export type PlanStatus =
  | 'REVIEW_READY'
  | 'APPROVED_FOR_EXECUTION'
  | 'CHANGE_REQUESTED'
  | 'CHANGED_AFTER_APPROVAL';

export type WorkPackageType =
  | 'SECURITY'
  | 'APPLICATION'
  | 'DATABASE'
  | 'STORAGE'
  | 'INTEGRATION'
  | 'TESTING'
  | 'DEPLOYMENT'
  | 'DOCUMENTATION';

export type TaskStatus = 'PLANNED' | 'IN_PROGRESS' | 'COMPLETED' | 'BLOCKED' | 'FAILED';
export type ExecutionMode = 'LOCAL_RUNTIME' | 'PLAN_ONLY' | 'REAL_CLOUD';
export type AutomationLevel = 'AUTO' | 'SEMI_AUTO' | 'MANUAL';
export type DeliveryStage = 'PU' | 'IFT' | 'UAT' | 'PROD';

export interface DerivedFrom {
  type: string;
  id: string;
}

export interface ImplementationEstimate {
  effortValue: number;
  effortUnit: 'PERSON_DAYS' | 'PERSON_HOURS' | 'STORY_POINTS';
  source: 'RULE_BASED' | 'ESTIMATED' | 'HISTORICAL';
  confidence: number;
}

export interface Task {
  taskId: string;
  workPackageId: string;
  title: string;
  description: string;
  category: string;
  status: TaskStatus;
  priority: number;
  executionMode: ExecutionMode;
  dependencies: string[];
  inputs: string[];
  outputs: string[];
  acceptanceCriteria: string[];
  evidenceRequirements: string[];
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  estimatedEffort: ImplementationEstimate;
  ownerRole: string;
  automation: AutomationLevel;
  derivedFrom: DerivedFrom[];
  deliveryStage: DeliveryStage;
  localValidatable: boolean;
}

export interface Dependency {
  depId: string;
  fromPackage: string;
  toPackage: string;
  description: string;
}

export interface WorkPackage {
  packageId: string;
  planId: string;
  title: string;
  description: string;
  packageType: WorkPackageType;
  tasks: Task[];
  dependencies: string[];
  parallelGroup: string;
  status: TaskStatus;
  estimatedEffort: ImplementationEstimate;
}

export interface Milestone {
  milestoneId: string;
  name: string;
  description: string;
  dependsOn: string[];
  completed: boolean;
}

export interface Risk {
  riskId: string;
  title: string;
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  probability: number;
  impact: number;
  mitigation: string;
  category: string;
  affectedTasks: string[];
}

export interface Blocker {
  blockerId: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  description: string;
  affectedTasks: string[];
  resolutionRequired: string;
}

export interface Gate {
  gateId: string;
  name: string;
  state: 'PASS' | 'PENDING' | 'FAIL';
  description: string;
}

export interface ImplementationPlan {
  planId: string;
  designId: string;
  designRevision: number;
  status: PlanStatus;
  createdAt: string;
  updatedAt: string;
  summary: string;
  workPackages: WorkPackage[];
  dependencies: Dependency[];
  milestones: Milestone[];
  risks: Risk[];
  blockers: Blocker[];
  gates: Gate[];
  openQuestions: string[];
  baselineChecksums: {
    requirements: string;
    architecture: string;
    flow: string;
  };
  planChecksum: string;
  criticalPath: string[];
  criticalPathDuration: string;
  readiness: string;
  approvedBy: string;
  approvedAt: string;
}

export interface PlanSummary {
  planId: string;
  designId: string;
  designRevision: number;
  status: PlanStatus;
  createdAt: string;
  readiness: string;
  packageCount: number;
  taskCount: number;
  dependencyCount: number;
  blockerCount: number;
  riskCount: number;
}

export interface PMHandoff {
  contractVersion: string;
  planId: string;
  workPackages: WorkPackage[];
  milestones: Milestone[];
  dependencies: Dependency[];
  criticalPath: string[];
  totalEstimate: ImplementationEstimate;
}

export interface QATestItem {
  taskId: string;
  title: string;
  acceptanceCriteria: string[];
  evidenceRequirements: string[];
  scenarioReferences: string[];
  riskLevel: string;
  localValidatable: boolean;
}

export interface QAHandoff {
  contractVersion: string;
  planId: string;
  testItems: QATestItem[];
}

/* Schedule mode */
export type ScheduleMode = 'RELAXED' | 'FIT';
