/* API → UI model mapping. Fails loudly if backend contract changes. */

import type { ImplementationPlan, PlanSummary, PMHandoff, QAHandoff } from './implementationTypes';

const API = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_API_URL) || '';

async function fetchJson(url: string, init?: RequestInit) {
  const r = await fetch(API + url, init);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${url}`);
  return r.json();
}

/** Create an implementation plan for a BASELINE_FROZEN design. */
export async function createPlan(designId: string): Promise<{ plan: ImplementationPlan }> {
  return fetchJson(`/api/v1/designs/${designId}/implementation-plan`, { method: 'POST' });
}

/** Get full implementation plan. */
export async function getPlan(planId: string): Promise<{ plan: ImplementationPlan }> {
  return fetchJson(`/api/v1/implementation-plans/${planId}`);
}

/** Get work packages for a plan. */
export async function getWorkPackages(planId: string): Promise<{ workPackages: ImplementationPlan['workPackages'] }> {
  return fetchJson(`/api/v1/implementation-plans/${planId}/work-packages`);
}

/** Get dependencies + critical path. */
export async function getDependencies(planId: string): Promise<{ dependencies: ImplementationPlan['dependencies']; criticalPath: string[]; cycles: string[][] }> {
  return fetchJson(`/api/v1/implementation-plans/${planId}/dependencies`);
}

/** Get readiness detail. */
export async function getReadiness(planId: string): Promise<{ readiness: string; blockers: ImplementationPlan['blockers']; gates: ImplementationPlan['gates']; risks: ImplementationPlan['risks']; openQuestions: string[] }> {
  return fetchJson(`/api/v1/implementation-plans/${planId}/readiness`);
}

/** Approve plan. */
export async function approvePlan(planId: string, approvedBy: string): Promise<{ plan: ImplementationPlan }> {
  return fetchJson(`/api/v1/implementation-plans/${planId}/approve?approved_by=${encodeURIComponent(approvedBy)}`, { method: 'POST' });
}

/** Request change. */
export async function requestChange(planId: string, change: { comment: string; affectedPackage?: string; affectedTask?: string }): Promise<{ plan: ImplementationPlan }> {
  return fetchJson(`/api/v1/implementation-plans/${planId}/request-change`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(change),
  });
}

/** Get PM handoff. */
export async function getPMHandoff(planId: string): Promise<PMHandoff> {
  return fetchJson(`/api/v1/implementation-plans/${planId}/handoff/pm`);
}

/** Get QA handoff. */
export async function getQAHandoff(planId: string): Promise<QAHandoff> {
  return fetchJson(`/api/v1/implementation-plans/${planId}/handoff/qa`);
}

/** Validate API contract: check required fields exist on plan response. */
export function validatePlanContract(plan: ImplementationPlan): string[] {
  const required: string[] = [
    'planId', 'designId', 'designRevision', 'status',
    'workPackages', 'dependencies', 'criticalPath',
    'readiness', 'blockers', 'risks', 'gates', 'planChecksum',
  ];
  const missing = required.filter(k => !(k in plan));
  return missing;
}

/** Derive summary stats from full plan. */
export function deriveSummary(plan: ImplementationPlan): PlanSummary {
  return {
    planId: plan.planId,
    designId: plan.designId,
    designRevision: plan.designRevision,
    status: plan.status,
    createdAt: plan.createdAt,
    readiness: plan.readiness,
    packageCount: plan.workPackages.length,
    taskCount: plan.workPackages.reduce((s, wp) => s + wp.tasks.length, 0),
    dependencyCount: plan.dependencies.length,
    blockerCount: plan.blockers.length,
    riskCount: plan.risks.length,
  };
}
