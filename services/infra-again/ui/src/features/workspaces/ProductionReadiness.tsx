
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
export default function ProductionReadiness({ actor, wsId }:{actor:{name:string;role:string};wsId:string}) {
  const [list,setList]=useState<any[]>([]);
  const [promos,setPromos]=useState<any[]>([]);
  const [uats,setUats]=useState<any[]>([]);
  const [rbs,setRbs]=useState<any[]>([]);
  const [msg,setMsg]=useState('');
  const [form,setForm]=useState({promotionId:'',uatId:'',rollbackPlanId:'',planId:'',packageId:'',planChecksum:'cs1',packageChecksum:'cs1'});
  const load=()=>{api.readinessList().then((d:any)=>setList(d.readinessRecords||[])).catch(()=>{});api.promotions().then((d:any)=>setPromos(d.promotions||[])).catch(()=>{});api.uats().then((d:any)=>setUats(d.uats||[])).catch(()=>{});api.rollbacks().then((d:any)=>setRbs(d.rollbackPlans||[])).catch(()=>{});};
  useEffect(()=>{load();},[]);
  const evaluate=async()=>{try{const r=await api.evaluateReadiness(form);setMsg('Result: '+r.readiness.readinessDecision+' ('+r.readiness.blocks.length+' blockers)');load();}catch(e:any){setMsg('Error: '+e.message);}};
  const latest=list[0];
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Production Readiness</div><h2 className="page-title">Production Eligibility</h2><p className="page-subtitle">Evaluates all gates. READY confirms eligibility only \u2014 PRODUCTION remains BLOCKED.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    <div className="panel mb-md"><div className="panel-title mb-sm">Evaluate Readiness</div>
      <div className="grid-2">{[{k:'promotionId',label:'Promotion',items:promos},{k:'uatId',label:'UAT',items:uats},{k:'rollbackPlanId',label:'Rollback',items:rbs}].map(f=>(<select key={f.k} className="form-select" value={(form as any)[f.k]} onChange={e=>setForm({...form,[f.k]:e.target.value})}><option value="">-- {f.label} --</option>{f.items.map((i:any)=><option key={i.promotionId||i.uatId||i.rollbackId} value={i.promotionId||i.uatId||i.rollbackId}>{(i.promotionId||i.uatId||i.rollbackId)} ({i.status})</option>)}</select>))}</div>
      <button className="btn btn-primary" onClick={evaluate}>Evaluate Readiness</button>
    </div>
    {latest&&<div className="panel mb-md" style={{textAlign:'center',padding:24}}><div style={{fontSize:22,fontWeight:700,color:latest.readinessDecision==='READY'?'var(--success)':'var(--danger)'}}>{latest.readinessDecision}</div><div className="text-muted mt-sm" style={{fontSize:11}}>Production Readiness Status</div><div className="mt-md"><span className="badge badge-danger">PRODUCTION EXECUTION: BLOCKED</span></div><div className="text-muted mt-sm" style={{fontSize:10}}>Readiness confirms eligibility only. Future AIRLOCK required.</div></div>}
    {list.length===0&&!latest&&<div className="panel empty-state"><div className="empty-state-title">No readiness evaluation</div></div>}
  </div>);
}
