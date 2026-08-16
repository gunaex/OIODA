
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
interface Props { actor:{name:string;role:string}; wsId:string; }
export default function PromotionCenter({ actor, wsId }: Props) {
  const [promos,setPromos]=useState<any[]>([]);
  const [envs,setEnvs]=useState<any[]>([]);
  const [msg,setMsg]=useState('');
  const [show,setShow]=useState(false);
  const [form,setForm]=useState({sourceEnvId:'',targetEnvId:'',planChecksum:'',packageChecksum:''});
  const load=()=>{api.promotions().then((d:any)=>setPromos(d.promotions||[])).catch(()=>{});api.environments().then((d:any)=>{setEnvs(d.environments||[]);const e=d.environments||[];if(!form.sourceEnvId&&e.length>0)setForm(f=>({...f,sourceEnvId:e[0].environmentId,targetEnvId:e.length>1?e[1].environmentId:''}));}).catch(()=>{});};
  useEffect(()=>{load();},[]);
  const create=async()=>{try{await api.createPromotion({...form,requestedBy:actor.name});setMsg('Promotion created');load();setShow(false);}catch(e:any){setMsg('Error: '+e.message);}};
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Promotion Center</div><div className="flex-between"><h2 className="page-title">Environment Promotion</h2><button className="btn btn-primary" onClick={()=>setShow(!show)}>+ Request Promotion</button></div><p className="page-subtitle">SANDBOX \u2192 CONTROLLED_REAL \u2192 PRODUCTION. Promotion is NOT execution.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    {show&&(<div className="panel mb-md"><div className="panel-title mb-sm">Request Promotion</div><div className="grid-2">{['sourceEnvId','targetEnvId'].map(k=>(<select key={k} className="form-select" value={(form as any)[k]} onChange={e=>setForm({...form,[k]:e.target.value})}>{envs.map((e:any)=><option key={e.environmentId} value={e.environmentId}>{e.classification}</option>)}</select>))}</div><div className="flex-row gap-sm"><button className="btn btn-primary" onClick={create}>Request</button><button className="btn btn-secondary" onClick={()=>setShow(false)}>Cancel</button></div></div>)}
    <div className="panel"><div className="panel-header"><div className="panel-title">Promotions</div></div>
      {promos.length===0?<div className="empty-state"><div className="empty-state-title">No promotions yet</div></div>:<table className="data-table"><thead><tr><th>ID</th><th>From\u2192To</th><th>Status</th><th>Actions</th></tr></thead><tbody>{promos.map((p:any)=>(<tr key={p.promotionId}><td className="mono">{p.promotionId}</td><td className="text-secondary" style={{fontSize:11}}>{p.sourceEnvClass} \u2192 {p.targetEnvClass}</td><td><span className={`badge ${p.status==='APPROVED'?'badge-success':p.status==='PENDING_APPROVAL'?'badge-warning':'badge-neutral'}`}>{p.status}</span></td><td className="flex-row gap-xs">{p.status==='PENDING_APPROVAL'&&<><button className="btn btn-primary btn-sm" onClick={async()=>{try{await api.approvePromotion(p.promotionId,actor.name);load();setMsg('Approved');}catch(e:any){setMsg('Error: '+e.message);}}}>Approve</button><button className="btn btn-danger btn-sm" onClick={async()=>{try{await api.rejectPromotion(p.promotionId);load();}catch(e:any){setMsg('Error: '+e.message);}}}>Reject</button></>}</td></tr>))}</tbody></table>}
    </div>
  </div>);
}
