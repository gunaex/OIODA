
import { useState, useEffect, useContext } from 'react';
import { api } from '../../lib/api';
import { ActorCtx } from '../../App';

interface Props { onNavigate:(v:any)=>void; wsId:string; wsName:string; onWsChange:(id:string,name:string)=>void; }

export default function FlightDeck({ onNavigate, wsId, wsName, onWsChange }: Props) {
  const { actor } = useContext(ActorCtx);
  const [ws, setWs] = useState<any>(null);
  const [designs, setDesigns] = useState<any[]>([]);
  const [promos, setPromos] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => Promise.all([
    api.workspaces().catch(()=>({workspaces:[]})),
    api.designs().catch(()=>({designs:[]})),
    api.promotions().catch(()=>({promotions:[]})),
    api.runs().catch(()=>({runs:[]})),
  ]).then(([w,d,p,r])=>{
    const wss = w.workspaces||[];
    if (wss.length>0 && !wsId) { const w0=wss[0]; onWsChange(w0.workspaceId, w0.name); }
    const cw = wss.find((x:any)=>x.workspaceId===wsId) || null;
    setWs(cw); setDesigns(d.designs||[]); setPromos(p.promotions||[]);
    setPlans((r as any).plans||(r as any).implementation_plans||[]);
    setLoading(false);
  });
  useEffect(()=>{load();},[wsId]);
  if (loading) return <div className="loading">Loading\u2026</div>;

  const currentDesign = ws?.currentDesignId ? designs.find((d:any)=>(d.id||d.designId)===ws.currentDesignId) : null;
  const designAccepted = currentDesign?.status==='ACCEPTED'||currentDesign?.status==='BASELINE_FROZEN';
  const hasPlan = plans.length>0;
  const planApproved = plans.some((p:any)=>p.status==='APPROVED_FOR_EXECUTION');
  const hasPromo = promos.length>0;
  const promoApproved = promos.some((p:any)=>p.status==='APPROVED');

  const stages = [
    {id:'design',label:'Design',done:!!currentDesign,active:!currentDesign},
    {id:'accept',label:'Accept',done:designAccepted,active:!!currentDesign&&!designAccepted},
    {id:'plan',label:'Plan',done:hasPlan,active:designAccepted&&!hasPlan},
    {id:'approve',label:'Approve',done:planApproved,active:hasPlan&&!planApproved},
    {id:'package',label:'Package',done:false,active:planApproved},
    {id:'execute',label:'Execute',done:false,active:false},
    {id:'observe',label:'Observe',done:false,active:false},
    {id:'validate',label:'Validate',done:false,active:false},
    {id:'verify',label:'Verify',done:false,active:false},
    {id:'evidence',label:'Evidence',done:false,active:false},
    {id:'promote',label:'Promote',done:hasPromo,active:false},
    {id:'rollback',label:'Rollback',done:false,active:hasPromo&&!false},
    {id:'uat',label:'UAT',done:false,active:false},
    {id:'readiness',label:'Readiness',done:false,active:false},
  ];

  const navMap:Record<string,string>={design:'architecture',accept:'architecture',plan:'implementation',approve:'implementation',package:'execution',execute:'execution',promote:'promotion',rollback:'recovery',uat:'uat',readiness:'prod-readiness'};

  let nextAction='Create Architecture Design';let nextView='architecture';
  if(currentDesign&&!designAccepted){nextAction='Accept Design';nextView='architecture';}
  else if(designAccepted&&!hasPlan){nextAction='Generate Implementation Plan';nextView='implementation';}
  else if(hasPlan&&!planApproved){nextAction='Approve Implementation Plan';nextView='implementation';}
  else if(planApproved&&!hasPromo){nextAction='Create Execution Package';nextView='execution';}
  else if(hasPromo&&!promoApproved){nextAction='Approve Promotion';nextView='promotion';}
  else if(promoApproved){nextAction='Evaluate Production Readiness';nextView='prod-readiness';}

  return (
    <div className="page">
      <div className="mb-lg">
        <div className="page-eyebrow">Infrastructure Flight Deck</div>
        <h2 className="page-title">INFRA-AGAIN</h2>
        <p className="page-subtitle">Infrastructure control center — Design, Plan, Execute, Verify, Promote.</p>
      </div>

      {/* Current Work */}
      <div className="panel mb-md">
        <div className="flex-between" style={{flexWrap:'wrap',gap:8}}>
          <div>
            <div style={{fontSize:14,fontWeight:600,color:'var(--text-primary)'}}>{ws?.name||'No active workspace'}</div>
            <div className="flex-row gap-sm" style={{marginTop:4,fontSize:11,color:'var(--text-secondary)'}}>
              {currentDesign ? <><span>Design:</span><span className="mono">{currentDesign.id||currentDesign.designId}</span><span className="badge badge-success">{currentDesign.status}</span></> : <span className="text-muted">No design selected</span>}
              {ws?.selectedProvider ? <span className="text-muted">| Provider: {ws.selectedProvider}</span> : ''}
              {ws?.selectedPlatform ? <span className="text-muted">| Platform: {ws.selectedPlatform}</span> : ''}
              {ws?.selectedFidelity ? <span className="text-muted">| Fidelity: {ws.selectedFidelity}</span> : ''}
            </div>
          </div>
          <div className="flex-row gap-xs">
            <span className="badge badge-warning">SANDBOX: ASK</span>
            <span className="badge badge-danger">CR: BLOCK</span>
            <span className="badge badge-danger">PROD: BLOCK</span>
          </div>
        </div>
      </div>

      {/* Lifecycle */}
      <div className="panel mb-md">
        <div className="panel-header"><div className="panel-title">Lifecycle</div></div>
        <div className="lifecycle">
          {stages.map((s,i)=>{
            let dotCls='available', lineCls='pending', labelCls='available';
            if(s.done){ dotCls='complete'; lineCls='complete'; labelCls='complete'; }
            else if(s.active){ dotCls='active'; labelCls='active'; }
            else if(i>0&&stages[i-1].done){ dotCls='available'; labelCls='available'; }
            if(i>0&&stages[i-1].done) lineCls='complete';
            return (
              <div key={s.id} className="lifecycle-stage">
                {i>0 && <div className={`lifecycle-line ${lineCls}`}/>}
                <button className="lifecycle-step" onClick={()=>{if(navMap[s.id]) onNavigate(navMap[s.id]);}}>
                  <div className={`lifecycle-dot ${dotCls}`}/>
                  <span className={`lifecycle-label ${labelCls}`}>{s.label}</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Next Action + Safety */}
      <div className="grid-2 mb-md">
        <button onClick={()=>onNavigate(nextView)} className="panel" style={{textAlign:'left',cursor:'pointer',borderColor:'var(--accent)',background:'var(--accent-soft)'}}>
          <div className="page-eyebrow">Next Action</div>
          <div style={{fontSize:14,fontWeight:600,color:'var(--accent)',marginTop:4}}>{nextAction}</div>
          <div style={{fontSize:11,color:'var(--accent)',marginTop:6}}>Go to workspace →</div>
        </button>
        <div className="panel">
          <div className="panel-title mb-sm">Safety</div>
          <div className="flex-col" style={{gap:3}}>
            {[{l:'SANDBOX',s:'ASK',c:'warning'},{l:'CONTROLLED REAL',s:'BLOCK',c:'danger'},{l:'PRODUCTION',s:'BLOCK',c:'danger'}].map(x=>(
              <div key={x.l} className="flex-between" style={{fontSize:11}}><span className="text-secondary">{x.l}</span><span className={`badge badge-${x.c}`}>{x.s}</span></div>
            ))}
            <div style={{borderTop:'1px solid var(--border-subtle)',marginTop:4,paddingTop:4,fontSize:11}} className="flex-between"><span className="text-secondary">REAL CLOUD</span><span className="badge badge-neutral">DEFERRED</span></div>
          </div>
        </div>
      </div>

      {/* Empty/Create */}
      {!ws && (
        <div className="panel empty-state">
          <div className="empty-state-title">No active workspace</div>
          <div className="empty-state-desc">Create a workspace to begin infrastructure operations.</div>
          <button className="btn btn-primary mt-md" onClick={async()=>{
            try{const r=await api.createWorkspace({name:'INFRA-AGAIN Workspace',provider:'ON_PREM',platform:'NATIVE_VM',fidelity:'LOCAL_RUNTIME'});
            onWsChange(r.workspace.workspaceId,r.workspace.name);}catch(e){}
          }}>Create Workspace</button>
        </div>
      )}
    </div>
  );
}
