
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
interface Props { actor:{name:string;role:string}; wsId:string; }
export default function ExecutionCenter({ actor, wsId }: Props) {
  const [runs,setRuns]=useState<any[]>([]);
  const [plans,setPlans]=useState<any[]>([]);
  const [msg,setMsg]=useState('');
  const [sel,setSel]=useState<any>(null);
  const load=()=>{api.runs().then((d:any)=>{setRuns(d.runs||[]);setPlans(d.plans||(d as any).implementation_plans||[]);}).catch(()=>{});};
  useEffect(()=>{load();},[]);
  const approved=plans.filter((p:any)=>p.status==='APPROVED_FOR_EXECUTION');
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Execution Center</div><h2 className="page-title">Execution & Verification</h2><p className="page-subtitle">Executor Success \u2260 Verified Success. Every stage independently validated.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    <div className="panel mb-md"><div className="panel-title mb-sm">Execution Pipeline</div><div className="grid-5">{['PLAN','EXECUTOR','OBSERVER','VALIDATOR','VERIFIER'].map(s=>(<div key={s} className="panel" style={{textAlign:'center',background:'var(--bg-elevated)'}}><div style={{fontSize:10,color:'var(--text-muted)',textTransform:'uppercase',letterSpacing:'0.05em'}}>{s}</div></div>))}</div></div>
    <div className="panel mb-md"><div className="panel-title mb-sm">Create Package & Execute</div>
      {approved.length===0?<div className="text-muted" style={{fontSize:11}}>No approved plans. Approve a plan in Implementation first.</div>:
      <div className="flex-row gap-sm" style={{flexWrap:'wrap'}}>{approved.slice(0,5).map((p:any)=>(<button key={p.id||p.planId} className="btn btn-primary" onClick={async()=>{try{const pkg=await api.createPackage(p.id||p.planId);const pkgId=pkg.id||pkg.packageId;setMsg('Package: '+pkgId);await api.preflight(pkgId);setMsg('Preflight passed. Executing...');const run=await api.execute(pkgId);setMsg('Run: '+((run as any).runId||(run as any).id||'OK'));load();}catch(e:any){setMsg('Error: '+e.message);}}}>Execute {((p as any).id||(p as any).planId||'').slice(0,12)}</button>))}</div>}
    </div>
    <div className="panel"><div className="panel-header"><div className="panel-title">Runs ({runs.length})</div></div>
      {runs.length===0?<div className="empty-state"><div className="empty-state-title">No execution runs</div></div>:<table className="data-table"><thead><tr><th>Run ID</th><th>Status</th><th>Fidelity</th><th></th></tr></thead><tbody>{runs.map((r:any)=>(<tr key={r.runId||r.id}><td className="mono">{r.runId||r.id}</td><td><span className={`badge ${r.status==='COMPLETED'?'badge-success':'badge-info'}`}>{r.status}</span></td><td className="text-secondary" style={{fontSize:10}}>{r.fidelity||'-'}</td><td><button className="btn btn-ghost btn-sm" onClick={()=>setSel(r)}>View</button></td></tr>))}</tbody></table>}
    </div>
    {sel&&<div className="modal-overlay" onClick={()=>setSel(null)}><div className="modal-content" onClick={e=>e.stopPropagation()}><div className="flex-between mb-sm"><div style={{fontWeight:600}}>Run: <span className="mono">{sel.runId||sel.id}</span></div><button className="btn btn-ghost" onClick={()=>setSel(null)}>&times;</button></div><div className="grid-2" style={{fontSize:11}}><div><span className="text-muted">Status:</span> {sel.status}</div><div><span className="text-muted">Fidelity:</span> {sel.fidelity||'-'}</div><div><span className="text-muted">Validation:</span> {sel.validation?.result||'-'}</div><div><span className="text-muted">Verification:</span> {sel.verification?.result||'-'}</div></div></div></div>}
  </div>);
}
