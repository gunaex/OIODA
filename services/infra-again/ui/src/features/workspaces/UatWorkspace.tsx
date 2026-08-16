
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
export default function UatWorkspace({ actor, wsId }:{actor:{name:string;role:string};wsId:string}) {
  const [uats,setUats]=useState<any[]>([]);
  const [msg,setMsg]=useState('');
  const [show,setShow]=useState(false);
  const [form,setForm]=useState({scope:'',acceptanceCriteria:''});
  const load=()=>api.uats().then((d:any)=>setUats(d.uats||[])).catch(()=>{});
  useEffect(()=>{load();},[]);
  const create=async()=>{try{await api.createUat({...form,requestedBy:actor.name});setMsg('UAT created');load();setShow(false);}catch(e:any){setMsg('Error: '+e.message);}};
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">UAT Workspace</div><div className="flex-between"><h2 className="page-title">User Acceptance Testing</h2><button className="btn btn-primary" onClick={()=>setShow(!show)}>+ Create UAT</button></div><p className="page-subtitle">Production eligibility requires UAT PASSED + SoD.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    {show&&(<div className="panel mb-md"><div className="panel-title mb-sm">New UAT</div><input className="form-input" placeholder="Scope" value={form.scope} onChange={e=>setForm({...form,scope:e.target.value})}/><input className="form-input" placeholder="Acceptance criteria" value={form.acceptanceCriteria} onChange={e=>setForm({...form,acceptanceCriteria:e.target.value})}/><div className="flex-row gap-sm"><button className="btn btn-primary" onClick={create}>Create</button><button className="btn btn-secondary" onClick={()=>setShow(false)}>Cancel</button></div></div>)}
    <div className="panel"><div className="panel-header"><div className="panel-title">UAT Records</div></div>
      {uats.length===0?<div className="empty-state"><div className="empty-state-title">No UAT records</div></div>:<div className="flex-col gap-sm">{uats.map((u:any)=>(<div key={u.uatId} className="panel" style={{background:'var(--bg-elevated)'}}><div className="flex-between mb-sm"><span className="mono">{u.uatId}</span><span className={`badge ${u.status==='PASSED'?'badge-success':u.status==='FAILED'?'badge-danger':'badge-neutral'}`}>{u.status}</span></div><div className="text-secondary mb-sm" style={{fontSize:11}}>Scope: {u.scope||'-'} \u00b7 Performed: {u.performedBy||'-'} \u00b7 Approved: {u.approvedBy||'-'}</div>{u.status!=='PASSED'&&u.status!=='FAILED'&&<div className="flex-row gap-xs"><button className="btn btn-success btn-sm" style={{background:'var(--success)',color:'#000'}} onClick={async()=>{try{await api.passUat(u.uatId,actor.name,'approver');load();setMsg('UAT PASSED');}catch(e:any){setMsg('Error: '+e.message);}}}>PASS</button><button className="btn btn-danger btn-sm" onClick={async()=>{try{await api.failUat(u.uatId);load();}catch(e:any){setMsg('Error: '+e.message);}}}>FAIL</button></div>}</div>))}</div>}
    </div>
  </div>);
}
