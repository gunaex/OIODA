
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
interface Props { actor:{name:string;role:string}; wsId:string; }

// Phase N3 — minimal Implementation Plan Quality panel. Read-only display
// of whatever the API returns; never derives/overrides execution
// classification, status, or staleness itself (LLM/frontend cannot mark a
// task executable or a plan approved by local state alone).
const CLASS_TONE: Record<string, string> = {
  EXECUTABLE: 'badge-success', PLAN_ONLY: 'badge-warning',
  UNEXECUTABLE: 'badge-danger', BLOCKED: 'badge-danger', UNKNOWN: 'badge-neutral',
};
const STATUS_TONE: Record<string, string> = {
  APPROVED_FOR_EXECUTION: 'badge-success', REVIEW_READY: 'badge-info',
  BASELINE_INVALIDATED: 'badge-danger', CHANGE_REQUESTED: 'badge-warning',
  DRAFT: 'badge-neutral', GENERATED: 'badge-neutral', COMPLETED: 'badge-success',
};

function PlanDetail({ plan, status, onApprove, busy }: { plan: any; status: any; onApprove: () => void; busy: boolean }) {
  const byClass: Record<string, number> = status?.tasksByClassification || {};
  const executable = byClass.EXECUTABLE || 0;
  const planOnly = byClass.PLAN_ONLY || 0;
  const unsupported = (byClass.UNEXECUTABLE || 0) + (byClass.BLOCKED || 0);
  const total = status?.totalTasks ?? (plan.workPackages || []).reduce((n: number, w: any) => n + (w.tasks?.length || 0), 0);
  const fullyExecutable = total > 0 && executable === total;

  return (
    <div style={{ fontSize: 11 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
        <span className="mono" style={{ color: 'var(--text-primary)' }}>{plan.planId}</span>
        <span className={`badge ${STATUS_TONE[status?.status || plan.status] || 'badge-neutral'}`} style={{ fontSize: 9 }}>
          {status?.status || plan.status}
        </span>
        {status?.stale && <span className="badge badge-danger" style={{ fontSize: 9 }}>STALE</span>}
        {plan.dependencyCycleDetected && <span className="badge badge-danger" style={{ fontSize: 9 }}>DEPENDENCY CYCLE</span>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, marginBottom: 8, fontSize: 10 }}>
        <div>Architecture Rev: <span style={{ color: 'var(--text-primary)' }}>{status?.architectureRevision ?? plan.architectureRevision}</span></div>
        <div>Target Fidelity: <span style={{ color: 'var(--text-primary)' }}>{status?.targetFidelity || plan.targetFidelity || '-'}</span></div>
        <div>Provider Intel: <span className="mono" style={{ fontSize: 9 }}>{status?.providerIntelligenceVersion || plan.providerIntelligenceVersion || '-'}</span></div>
        <div>Feasibility: <span className="mono" style={{ fontSize: 9 }}>{status?.feasibilityDigest || plan.feasibilityDigest || '-'}</span></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 4, marginBottom: 8, fontSize: 10 }}>
        <div>Tasks: {total}</div>
        <div>Executable: {executable}</div>
        <div>Plan Only: {planOnly}</div>
        <div>Unsupported: {unsupported}</div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <span className={`badge ${fullyExecutable ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: 9 }}>
          {fullyExecutable ? 'FULLY EXECUTABLE' : 'NOT FULLY EXECUTABLE'}
        </span>
      </div>

      {status?.staleReasons?.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: 'var(--danger)', fontWeight: 500, marginBottom: 2 }}>Stale — Reassessment Required</div>
          {status.staleReasons.map((r: string, i: number) => <div key={i} style={{ color: 'var(--text-muted)', paddingLeft: 4 }}>• {r}</div>)}
        </div>
      )}

      {(plan.blockers || []).length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: 'var(--danger)', fontWeight: 500, marginBottom: 2 }}>Blocking</div>
          {plan.blockers.map((b: any, i: number) => <div key={i} style={{ color: 'var(--text-muted)', paddingLeft: 4 }}>• {b.description}</div>)}
        </div>
      )}

      <div style={{ marginBottom: 8 }}>
        <div className="panel-title" style={{ fontSize: 10, marginBottom: 4 }}>Packages</div>
        <table style={{ width: '100%', fontSize: 9, borderCollapse: 'collapse' }}>
          <thead><tr style={{ color: 'var(--text-muted)' }}>
            <th style={{ textAlign: 'left', padding: 2 }}>Package</th><th style={{ textAlign: 'left', padding: 2 }}>Type</th>
            <th style={{ textAlign: 'left', padding: 2 }}>Readiness</th><th style={{ textAlign: 'left', padding: 2 }}>Tasks</th>
          </tr></thead>
          <tbody>
            {(plan.workPackages || []).map((w: any) => (
              <tr key={w.packageId} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '3px 2px' }}>{w.title}</td>
                <td style={{ padding: '3px 2px' }}>{w.packageType}</td>
                <td style={{ padding: '3px 2px' }}>
                  <span className={`badge ${CLASS_TONE[w.executionReadiness] || 'badge-neutral'}`} style={{ fontSize: 8 }}>{w.executionReadiness}</span>
                </td>
                <td style={{ padding: '3px 2px' }}>
                  {(w.tasks || []).map((t: any) => (
                    <span key={t.taskId} className={`badge ${CLASS_TONE[t.executionClassification] || 'badge-neutral'}`}
                      style={{ fontSize: 8, marginRight: 3 }} title={`${t.title} (deps: ${(t.dependencies||[]).join(', ') || 'none'})`}>
                      {t.executionClassification}
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(plan.dependencies || []).length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div className="panel-title" style={{ fontSize: 10, marginBottom: 4 }}>Dependencies</div>
          {plan.dependencies.map((d: any) => (
            <div key={d.depId} style={{ color: 'var(--text-muted)', paddingLeft: 4 }}>• {d.description}</div>
          ))}
        </div>
      )}

      {status?.status === 'REVIEW_READY' && !plan.dependencyCycleDetected && (
        <button className="btn btn-primary btn-sm" disabled={busy} onClick={onApprove}>Approve Plan</button>
      )}

      {(status?.status || plan.status) === 'APPROVED_FOR_EXECUTION' && <ExecutionPanel planId={plan.planId} />}
    </div>
  );
}

// Phase N4 — minimal AIRLOCK/execution panel. Shows Plan Approved →
// Execution Package created → AIRLOCK (preflight) result → Execution
// result, plus blockers/rejection reasons verbatim from the API. Never
// renders anything as "Verified Success" — that is N5's independent
// observer/validator/verifier concern, not something this phase or the
// executor itself can claim.
const CHECK_TONE: Record<string, string> = { PASS: 'badge-success', FAIL: 'badge-warning', BLOCK: 'badge-danger', NOT_APPLICABLE: 'badge-neutral' };
const TARGET_TYPES = ['fakecloud', 'kind', 'plan-only'];

function ExecutionPanel({ planId }: { planId: string }) {
  const [pkg, setPkg] = useState<any>(null);
  const [preflight, setPreflight] = useState<any>(null);
  const [execResult, setExecResult] = useState<any>(null);
  const [targetType, setTargetType] = useState('fakecloud');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<any>(null);

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
      <div className="panel-title" style={{ fontSize: 10, marginBottom: 6 }}>Execution (AIRLOCK)</div>

      {err && (
        <div style={{ marginBottom: 8, fontSize: 9, color: 'var(--danger)' }}>
          Rejected: {typeof err === 'string' ? err : JSON.stringify(err)}
        </div>
      )}

      {!pkg && (
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <select className="form-select" value={targetType} onChange={e => setTargetType(e.target.value)} style={{ fontSize: 10 }}>
            {TARGET_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={async () => {
            setBusy(true); setErr(null);
            try {
              const r = await api.createPackage(planId, { target_type: targetType, idempotency_key: `ui-${planId}` });
              setPkg(r.package);
            } catch (e: any) { setErr(e.message); }
            finally { setBusy(false); }
          }}>Create Execution Package</button>
        </div>
      )}

      {pkg && (
        <div style={{ fontSize: 10 }}>
          <div style={{ marginBottom: 6 }}>
            Package: <span className="mono">{pkg.executionPackageId}</span>{' '}
            <span className={`badge ${pkg.status === 'COMPLETED' ? 'badge-success' : 'badge-neutral'}`} style={{ fontSize: 8 }}>{pkg.status}</span>
          </div>

          {!preflight && (
            <button className="btn btn-secondary btn-sm" disabled={busy} onClick={async () => {
              setBusy(true); setErr(null);
              try {
                const r = await api.preflight(pkg.executionPackageId);
                setPreflight(r);
                setPkg((p: any) => ({ ...p, status: r.status }));
              } catch (e: any) { setErr(e.message); }
              finally { setBusy(false); }
            }}>Run Preflight (AIRLOCK)</button>
          )}

          {preflight && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ marginBottom: 4 }}>
                AIRLOCK Result: <span className={`badge ${preflight.status === 'PREFLIGHT_PASSED' ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: 8 }}>{preflight.status}</span>
              </div>
              {preflight.checks.filter((c: any) => c.status !== 'PASS').map((c: any) => (
                <div key={c.checkId} style={{ color: 'var(--danger)', paddingLeft: 4, fontSize: 9 }}>
                  • {c.name}: {c.status} — {c.message}
                </div>
              ))}
            </div>
          )}

          {preflight?.status === 'PREFLIGHT_PASSED' && !execResult && (
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={async () => {
              setBusy(true); setErr(null);
              try {
                const r = await api.execute(pkg.executionPackageId);
                setExecResult(r.result);
              } catch (e: any) { setErr(e.message); }
              finally { setBusy(false); }
            }}>Execute</button>
          )}

          {execResult && (
            <div style={{ marginTop: 8 }}>
              <div>Execution Result: <span className={`badge ${execResult.status === 'COMPLETED' ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: 8 }}>{execResult.status}</span></div>
              <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>
                Run: <span className="mono">{execResult.runId}</span> · {execResult.tasksPassed} passed · {execResult.tasksFailed} failed
              </div>
              <div style={{ fontSize: 8, color: 'var(--text-muted)', marginTop: 4 }}>
                (Executor-reported result only — independent verification is a separate later phase, not claimed here.)
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ImplementationWorkspace({ actor, wsId }: Props) {
  const [designs,setDesigns]=useState<any[]>([]);
  const [msg,setMsg]=useState('');
  const [plan, setPlan] = useState<any>(null);
  const [planStatus, setPlanStatus] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const load=()=>{api.designs().then((d:any)=>setDesigns(d.designs||[])).catch(()=>{});};
  useEffect(()=>{load();},[]);
  const accepted=designs.filter((d:any)=>d.status==='ACCEPTED'||d.status==='BASELINE_FROZEN');

  const refreshPlan = async (planId: string) => {
    const [p, s] = await Promise.all([api.getPlan(planId), api.getPlanStatus(planId)]);
    setPlan(p.plan); setPlanStatus(s);
  };

  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Implementation Workspace</div><h2 className="page-title">Implementation Plans</h2><p className="page-subtitle">From accepted design to executable plan.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    <div className="panel mb-md"><div className="panel-title mb-sm">Generate Plan</div>
      {accepted.length===0?<div className="text-muted" style={{fontSize:11}}>No accepted designs. Accept a design first in Architecture.</div>:
      <div className="flex-row gap-sm" style={{flexWrap:'wrap'}}>{accepted.slice(0,5).map((d:any)=>(<button key={d.id||d.designId} className="btn btn-primary" disabled={busy} onClick={async()=>{
        setBusy(true);
        try{
          const r=await api.createPlan(d.id||d.designId,'SIMULATED');
          const pid = r.plan?.planId || r.id || r.planId;
          setMsg('Plan generated: '+pid);
          await refreshPlan(pid);
          if(wsId)api.setWsPlan(wsId,pid).catch(()=>{});
        }catch(e:any){setMsg('Error: '+e.message);}
        finally{setBusy(false);}
      }}>Generate from {(d.name||(d.id||d.designId)).slice(0,16)}</button>))}</div>}
    </div>
    <div className="panel"><div className="panel-header"><div className="panel-title">Implementation Plan</div></div>
      {!plan ? <div className="empty-state"><div className="empty-state-title">No plan generated yet</div></div> :
        <PlanDetail plan={plan} status={planStatus} busy={busy} onApprove={async()=>{
          setBusy(true);
          try{ await api.approvePlan(plan.planId); setMsg('Plan approved'); await refreshPlan(plan.planId); }
          catch(e:any){ setMsg('Error: '+e.message); }
          finally{ setBusy(false); }
        }} />
      }
    </div>
  </div>);
}
