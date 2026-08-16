import React, { useState, useEffect } from 'react';
import type { ImplementationPlan, WorkPackage, ScheduleMode } from './model/implementationTypes';
import { createPlan, getPlan, approvePlan, requestChange, validatePlanContract } from './model/implementationMapper';
import PlanSummary from './components/PlanSummary';
import WorkPackageList, { WorkPackageDetails } from './components/WorkPackageList';
import DependencyGraph from './components/DependencyGraph';
import CriticalPathPanel from './components/CriticalPathPanel';
import ReadinessMatrix from './components/ReadinessMatrix';
import RiskBlockerPanel from './components/RiskBlockerPanel';
import ImplementationTimeline, { ScheduleModeToggle } from './components/ImplementationTimeline';
import PlanReviewPanel from './components/PlanReviewPanel';
import HandoffPanel from './components/HandoffPanel';

const API = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_API_URL) || '';

async function fetchJson(url: string, init?: RequestInit) {
  const r = await fetch(API + url, init);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export default function ImplementationPlanPage() {
  const [designId, setDesignId] = useState('');
  const [designs, setDesigns] = useState<any[]>([]);
  const [plan, setPlan] = useState<ImplementationPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedPkg, setSelectedPkg] = useState<WorkPackage | null>(null);
  const [scheduleMode, setScheduleMode] = useState<ScheduleMode>('RELAXED');
  const [contractErrors, setContractErrors] = useState<string[]>([]);

  // Load designs list
  useEffect(() => {
    fetchJson('/api/v1/designs').then(d => setDesigns(d.designs || [])).catch(() => {});
  }, []);

  const handleCreatePlan = async () => {
    if (!designId) return;
    setLoading(true); setError(''); setContractErrors([]);
    try {
      const result = await createPlan(designId);
      const p = result.plan;
      const missing = validatePlanContract(p);
      if (missing.length > 0) { setContractErrors(missing); }
      setPlan(p);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleLoadPlan = async (pid: string) => {
    setLoading(true); setError(''); setContractErrors([]);
    try {
      const result = await getPlan(pid);
      const p = result.plan;
      const missing = validatePlanContract(p);
      if (missing.length > 0) { setContractErrors(missing); }
      setPlan(p);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleApprove = async (approvedBy: string) => {
    if (!plan) return;
    setLoading(true); setError('');
    try {
      const result = await approvePlan(plan.planId, approvedBy);
      setPlan(result.plan);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleRequestChange = async (comment: string, affectedPackage?: string, affectedTask?: string) => {
    if (!plan) return;
    setLoading(true); setError('');
    try {
      const result = await requestChange(plan.planId, { comment, affectedPackage, affectedTask });
      setPlan(result.plan);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const frozenDesigns = designs.filter(d => d.status === 'BASELINE_FROZEN');
  const nonFrozenDesigns = designs.filter(d => d.status !== 'BASELINE_FROZEN');

  return (
    <div style={{ padding: 24, fontFamily: 'system-ui', maxWidth: 1100, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 4px' }}>📋 Implementation Planner</h1>
      <p style={{ color: '#6b7280', margin: '0 0 20px' }}>Phase 6 — Deterministic Implementation Planning</p>

      {/* Create Plan CTA */}
      {!plan && (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <h3 style={{ margin: '0 0 12px' }}>Create Implementation Plan</h3>

          {frozenDesigns.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#22c55e' }}>✅ BASELINE_FROZEN Designs</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {frozenDesigns.map(d => (
                  <button key={d.designId} onClick={() => { setDesignId(d.designId); handleCreatePlan(); }}
                    style={{ padding: '8px 16px', background: designId === d.designId ? '#3b82f6' : '#dcfce7', color: designId === d.designId ? '#fff' : '#166534', border: '1px solid #22c55e', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
                    {d.designId}: {d.metadata?.name || 'Unnamed'}
                  </button>
                ))}
              </div>
            </div>
          )}

          {nonFrozenDesigns.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#9ca3af' }}>🔒 Other Designs (must be accepted first)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {nonFrozenDesigns.map(d => (
                  <button key={d.designId} disabled
                    title="Accept and freeze the design before creating an implementation plan."
                    style={{ padding: '8px 16px', background: '#f3f4f6', color: '#9ca3af', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, cursor: 'not-allowed' }}>
                    {d.designId}: {d.metadata?.name || 'Unnamed'} ({d.status})
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4, fontStyle: 'italic' }}>
                Accept and freeze the design before creating an implementation plan.
              </div>
            </div>
          )}

          {designs.length === 0 && (
            <div style={{ color: '#9ca3af', fontSize: 13 }}>No designs yet. Create and freeze a design first.</div>
          )}
        </div>
      )}

      {/* Plan viewer */}
      {plan && (
        <>
          {/* Back button */}
          <button onClick={() => { setPlan(null); setSelectedPkg(null); }}
            style={{ padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 12, marginBottom: 16 }}>
            ← Back to designs
          </button>

          {/* Contract validation warning */}
          {contractErrors.length > 0 && (
            <div style={{ border: '1px solid #f59e0b', borderRadius: 8, padding: 10, marginBottom: 12, background: '#fffbeb', fontSize: 12, color: '#92400e' }}>
              ⚠️ API/UI contract mismatch — missing fields: {contractErrors.join(', ')}
            </div>
          )}

          {/* Loading / Error */}
          {loading && <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>⏳ Loading...</div>}
          {error && <div style={{ border: '1px solid #ef4444', borderRadius: 8, padding: 12, marginBottom: 12, background: '#fef2f2', color: '#ef4444', fontSize: 13 }}>Error: {error}</div>}

          {!loading && !error && (
            <>
              {/* Plan Summary */}
              <PlanSummary plan={plan} />

              {/* Review & Approval */}
              <PlanReviewPanel plan={plan} onApprove={handleApprove} onRequestChange={handleRequestChange} loading={loading} />

              {/* Schedule mode toggle */}
              <ScheduleModeToggle mode={scheduleMode} onChange={setScheduleMode} />

              {/* Dependency Graph */}
              <DependencyGraph dependencies={plan.dependencies} workPackages={plan.workPackages} criticalPath={plan.criticalPath} />

              {/* Critical Path */}
              <CriticalPathPanel criticalPath={plan.criticalPath} workPackages={plan.workPackages} />

              {/* Timeline (RELAXED/FIT) */}
              <ImplementationTimeline
                workPackages={plan.workPackages}
                milestones={plan.milestones}
                criticalPath={plan.criticalPath}
                mode={scheduleMode}
              />

              {/* Work Packages */}
              <WorkPackageList packages={plan.workPackages} onSelect={setSelectedPkg} selectedId={selectedPkg?.packageId} />
              {selectedPkg && <WorkPackageDetails wp={selectedPkg} />}

              {/* Readiness */}
              <ReadinessMatrix
                readiness={plan.readiness}
                gates={plan.gates}
                blockers={plan.blockers}
                risks={plan.risks}
                openQuestions={plan.openQuestions}
              />

              {/* Risks & Blockers */}
              <RiskBlockerPanel risks={plan.risks} blockers={plan.blockers} />

              {/* Handoff */}
              <HandoffPanel planId={plan.planId} />
            </>
          )}
        </>
      )}
    </div>
  );
}
