
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
