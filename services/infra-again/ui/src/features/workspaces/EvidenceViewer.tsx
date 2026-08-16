
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
export default function EvidenceViewer({ wsId }:{wsId:string}) {
  const [runs,setRuns]=useState<any[]>([]);
  useEffect(()=>{api.runs().then((d:any)=>setRuns(d.runs||[])).catch(()=>{});},[]);
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Evidence Viewer</div><h2 className="page-title">Execution Evidence</h2><p className="page-subtitle">Before/after state, observation, validation, verification. Evidence is first-class.</p></div>
    <div className="panel"><div className="panel-header"><div className="panel-title">Evidence Records</div></div>
      {runs.length===0?<div className="empty-state"><div className="empty-state-title">No evidence records</div><div className="empty-state-desc">Complete execution and verification first.</div></div>:<div className="flex-col gap-sm">{runs.map((r:any)=>(<div key={r.runId||r.id} className="panel" style={{background:'var(--bg-elevated)'}}><div className="flex-between mb-sm"><span className="mono">{r.runId||r.id}</span><span className={`badge ${r.status==='COMPLETED'?'badge-success':'badge-info'}`}>{r.status||'UNKNOWN'}</span></div><div className="grid-2" style={{fontSize:11}}><div><span className="text-muted">Validation:</span> {r.validation?.result||'-'}</div><div><span className="text-muted">Verification:</span> {r.verification?.result||'-'}</div></div></div>))}</div>}
    </div>
  </div>);
}
