
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
export default function RecoveryCenter({ actor, wsId }:{actor:{name:string;role:string};wsId:string}) {
  const [plans,setPlans]=useState<any[]>([]);
  const [msg,setMsg]=useState('');
  const [show,setShow]=useState(false);
  const [form,setForm]=useState({triggerConditions:'',rollbackSteps:'',expectedRecoveryState:''});
  const load=()=>api.rollbacks().then((d:any)=>setPlans(d.rollbackPlans||[])).catch(()=>{});
  useEffect(()=>{load();},[]);
  const create=async()=>{try{await api.createRollback({triggerConditions:[form.triggerConditions],rollbackSteps:[form.rollbackSteps],verificationSteps:[],expectedRecoveryState:form.expectedRecoveryState,owner:actor.name});setMsg('Rollback plan created');load();setShow(false);}catch(e:any){setMsg('Error: '+e.message);}};
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Recovery Center</div><div className="flex-between"><h2 className="page-title">Rollback & Recovery</h2><button className="btn btn-primary" onClick={()=>setShow(!show)}>+ Create Rollback</button></div><p className="page-subtitle">Rollback executor success \u2260 Recovery verified.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    {show&&(<div className="panel mb-md"><div className="panel-title mb-sm">New Rollback Plan</div><input className="form-input" placeholder="Trigger conditions" value={form.triggerConditions} onChange={e=>setForm({...form,triggerConditions:e.target.value})}/><input className="form-input" placeholder="Rollback steps" value={form.rollbackSteps} onChange={e=>setForm({...form,rollbackSteps:e.target.value})}/><input className="form-input" placeholder="Expected recovery state" value={form.expectedRecoveryState} onChange={e=>setForm({...form,expectedRecoveryState:e.target.value})}/><div className="flex-row gap-sm"><button className="btn btn-primary" onClick={create}>Create</button><button className="btn btn-secondary" onClick={()=>setShow(false)}>Cancel</button></div></div>)}
    <div className="panel"><div className="panel-header"><div className="panel-title">Rollback Plans</div></div>
      {plans.length===0?<div className="empty-state"><div className="empty-state-title">No rollback plans</div></div>:<div className="flex-col gap-sm">{plans.map((p:any)=>(<div key={p.rollbackId} className="panel" style={{background:'var(--bg-elevated)'}}><div className="flex-between mb-sm"><span className="mono">{p.rollbackId}</span><span className={`badge ${p.status==='APPROVED'?'badge-success':'badge-neutral'}`}>{p.status}</span></div><div className="text-secondary mb-sm" style={{fontSize:11}}>Recovery: {p.expectedRecoveryState||'-'} \u00b7 Owner: {p.owner||'-'}</div>{p.status==='DRAFT'&&<button className="btn btn-primary btn-sm" onClick={async()=>{try{await api.approveRollback(p.rollbackId,actor.name);load();setMsg('Approved');}catch(e:any){setMsg('Error: '+e.message);}}}>Approve</button>}</div>))}</div>}
    </div>
  </div>);
}
