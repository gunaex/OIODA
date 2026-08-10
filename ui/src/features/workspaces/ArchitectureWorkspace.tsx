
import { useState, useEffect, useCallback, useRef, useContext, lazy, Suspense } from 'react';
import { api } from '../../lib/api';
import { ActorCtx } from '../../App';
import { createExampleDesign, generateMermaid, type CanonicalDesign, type ArchitectureNode } from '../../lib/drawioEngine';

const ReactFlowStudio = lazy(() => import('./ReactFlowStudio'));

interface Props { actor: {name:string;role:string}; wsId: string; onWsChange: (id:string,name:string)=>void; }

type Engine = 'drawio' | 'reactflow';
const VIEWS = ['architecture','dataFlow','operationFlow','securityFlow'] as const;
type ViewName = typeof VIEWS[number];

export default function ArchitectureWorkspace({ actor, wsId, onWsChange }: Props) {
  const [engine, setEngine] = useState<Engine>('drawio');
  const [designs, setDesigns] = useState<any[]>([]);
  const [currentDesign, setCurrentDesign] = useState<any>(null);
  const [canonical, setCanonical] = useState<CanonicalDesign | null>(null);
  const [view, setView] = useState<ViewName>('architecture');
  const [selNode, setSelNode] = useState<ArchitectureNode | null>(null);
  const [msg, setMsg] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [createForm, setCreateForm] = useState({name:'',description:'',provider:'ON_PREM',platform:'NATIVE_VM',fidelity:'LOCAL_RUNTIME'});
  const [aiForm, setAiForm] = useState({objective:'',components:'',provider:'ON_PREM',platform:'NATIVE_VM'});
  const drawioRef = useRef<any>(null);
  const [drawioXml, setDrawioXml] = useState<string>('');
  const [drawioLoading, setDrawioLoading] = useState(true);
  const [drawioReady, setDrawioReady] = useState(false);

  const loadDesigns = () => api.designs().then((d:any)=>setDesigns(d.designs||[])).catch(()=>{});

  useEffect(()=>{loadDesigns();},[]);

  // Load canonical design when selected
  useEffect(()=>{
    if (!currentDesign) { setCanonical(null); setDrawioXml(''); return; }
    const did = currentDesign.id||currentDesign.designId;
    api.getDesign(did).then((d:any)=>{
      const flow = d.flow || d;
      // If design has draw.io XML, use it
      if (flow?.diagramDocument && flow?.diagramEngine==='drawio') {
        setCanonical(flow as CanonicalDesign);
        setDrawioXml(flow.diagramDocument);
        setDrawioLoading(false);
      } else {
        // Create canonical from design data
        const cd = createExampleDesign(currentDesign.provider||'ON_PREM');
        cd.designId = did;
        cd.title = currentDesign.name||'';
        cd.description = currentDesign.description||'';
        cd.provider = currentDesign.provider||'ON_PREM';
        cd.platform = currentDesign.platform||'NATIVE_VM';
        cd.status = currentDesign.status||'DRAFT';
        setCanonical(cd);
        // Generate initial draw.io XML via Mermaid
        const mm = generateMermaid(cd.nodes, cd.edges, 'architecture');
        setDrawioXml(''); // Clear to trigger reload
        setDrawioLoading(false);
      }
    }).catch(()=>{setDrawioLoading(false);});
  }, [currentDesign]);

  // Handle draw.io save
  const handleDrawioSave = useCallback((data: any) => {
    const xml = data.xml || data.data || '';
    if (!xml || !canonical) return;
    const updatedCanonical = { ...canonical, diagramDocument: xml, diagramEngine: 'drawio', updatedAt: new Date().toISOString() };
    setCanonical(updatedCanonical);
    setDrawioXml(xml);
    // Persist
    const did = currentDesign?.id||currentDesign?.designId;
    if (did) {
      api.post(`/api/v1/designs/${did}/update-flow`, { flow: updatedCanonical })
        .then(()=>setMsg('Design saved'))
        .catch((e:any)=>setMsg('Save error: '+e.message));
    }
  }, [canonical, currentDesign]);

  // Handle draw.io export (for programmatic save)
  const handleDrawioExport = useCallback((data: any) => {
    if (data.format === 'xmlsvg' || data.format === 'svg') {
      handleDrawioSave({ xml: data.xml || data.data });
    }
  }, [handleDrawioSave]);

  const createDesign = async () => {
    try {
      const r = await api.createDesign({name:createForm.name,description:createForm.description,provider:createForm.provider,platform:createForm.platform,fidelity:createForm.fidelity});
      const did = r.id||r.designId;
      setMsg('Design created: '+did); loadDesigns(); setShowCreate(false);
      if (wsId) api.setWsDesign(wsId, did).catch(()=>{});
    } catch(e:any) { setMsg('Error: '+e.message); }
  };

  const aiGenerate = async () => {
    if (!canonical) return;
    const did = currentDesign?.id||currentDesign?.designId;
    try {
      // Try AI generation endpoint
      const r = await api.post(`/api/v1/designs/${did}/ai-generate`, {brief:aiForm});
      // Convert AI flow to canonical
      const cd = createExampleDesign(aiForm.provider);
      cd.designId = did; cd.title = currentDesign?.name||'AI Generated';
      cd.provider = aiForm.provider; cd.platform = aiForm.platform;
      setCanonical(cd);
      const mm = generateMermaid(cd.nodes, cd.edges, 'architecture');
      setDrawioXml(''); // trigger reload with Mermaid
      setMsg('AI generated: '+cd.title); setShowAI(false); loadDesigns();
    } catch(e:any) { setMsg('AI error: '+e.message); }
  };

  const acceptDesign = async () => {
    if (!currentDesign) return;
    try { await api.acceptDesign(currentDesign.id||currentDesign.designId); loadDesigns(); setMsg('Design accepted'); } catch(e:any){setMsg('Error: '+e.message);}
  };

  const isFrozen = currentDesign?.status==='ACCEPTED'||currentDesign?.status==='BASELINE_FROZEN';
  const provider = canonical?.provider || currentDesign?.provider || 'ON_PREM';

  return (
    <div style={{display:'flex',height:'calc(100vh - 88px)',gap:0,overflow:'hidden'}}>
      {/* LEFT PANEL */}
      <div style={{width:220,minWidth:220,background:'var(--bg-surface)',borderRight:'1px solid var(--border-default)',display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{padding:12,borderBottom:'1px solid var(--border-default)'}}>
          <div className="panel-title">Designs</div>
          <button className="btn btn-primary btn-sm" style={{marginTop:8,width:'100%'}} onClick={()=>setShowCreate(!showCreate)}>+ New Design</button>
          <button className="btn btn-secondary btn-sm" style={{marginTop:4,width:'100%'}} onClick={()=>setShowAI(!showAI)}>AI Generate</button>
          {/* Engine toggle */}
          <div className="flex-row gap-xs" style={{marginTop:8}}>
            <button className={`btn btn-sm ${engine==='drawio'?'btn-primary':'btn-ghost'}`} style={{fontSize:9,flex:1}} onClick={()=>setEngine('drawio')}>draw.io</button>
            <button className={`btn btn-sm ${engine==='reactflow'?'btn-primary':'btn-ghost'}`} style={{fontSize:9,flex:1}} onClick={()=>setEngine('reactflow')}>React Flow</button>
          </div>
        </div>
        <div className="flex-col" style={{flex:1,overflow:'auto',padding:'4px 8px',gap:2}}>
          {designs.map((d:any)=>(
            <button key={d.id||d.designId} onClick={()=>setCurrentDesign(d)}
              style={{textAlign:'left',padding:'6px 8px',borderRadius:4,border:'none',cursor:'pointer',fontSize:11,
                background:(currentDesign?.id||currentDesign?.designId)===(d.id||d.designId)?'var(--bg-active)':'transparent',
                color:'var(--text-secondary)'}}>
              <div style={{fontWeight:500,color:'var(--text-primary)'}}>{(d.name||(d.id||d.designId)).slice(0,20)}</div>
              <div style={{fontSize:9,color:'var(--text-muted)'}}>{d.status||'DRAFT'} · {d.provider||'?'}</div>
            </button>
          ))}
        </div>
      </div>

      {/* CENTER — draw.io or React Flow */}
      <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{height:36,minHeight:36,background:'var(--bg-surface)',borderBottom:'1px solid var(--border-default)',display:'flex',alignItems:'center',padding:'0 12px',gap:8}}>
          <span style={{fontSize:11,fontWeight:600,color:'var(--text-primary)'}}>{canonical?.title||'No design'}</span>
          {currentDesign && <span className={`badge ${isFrozen?'badge-success':'badge-neutral'}`} style={{fontSize:9}}>{currentDesign.status||'DRAFT'}</span>}
          <span className="badge badge-info" style={{fontSize:9}}>{provider}</span>
          <div style={{flex:1}}/>
          {VIEWS.map(v=>(<button key={v} onClick={()=>setView(v)} className={`btn btn-sm ${view===v?'btn-primary':'btn-ghost'}`} style={{fontSize:10,textTransform:'capitalize'}}>{v.replace(/([A-Z])/g,' $1')}</button>))}
          {!isFrozen && <button className="btn btn-primary btn-sm" onClick={()=>drawioRef.current?.exportDiagram({format:'xmlsvg'})}>Save</button>}
          {!isFrozen && currentDesign && <button className="btn btn-sm" style={{background:'var(--success)',color:'#000'}} onClick={acceptDesign}>Accept</button>}
          {isFrozen && <span className="badge badge-success">FROZEN</span>}
        </div>
        <div style={{flex:1,background:'var(--bg-root)',position:'relative'}}>
          {!currentDesign ? (
            <div className="empty-state" style={{height:'100%'}}>
              <div className="empty-state-title">Select or create a design</div>
            </div>
          ) : engine==='drawio' ? (
            drawioLoading ? <div className="loading">Loading draw.io...</div> : (
              <DrawioEmbed
                ref={drawioRef}
                xml={drawioXml}
                onSave={handleDrawioSave}
                onExport={handleDrawioExport}
                urlParameters={{ libraries: false, saveAndExit: false, noExitBtn: true, noSaveBtn: false }}
                configuration={{ defaultFonts: ['system-ui'] }}
              />
            )
          ) : (
            <Suspense fallback={<div className="loading">Loading React Flow...</div>}>
              <ReactFlowStudio canonical={canonical} onSave={(c:CanonicalDesign)=>setCanonical(c)} />
            </Suspense>
          )}
        </div>
      </div>

      {/* RIGHT PANEL — Inspector */}
      <div style={{width:200,minWidth:200,background:'var(--bg-surface)',borderLeft:'1px solid var(--border-default)',display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{padding:12,borderBottom:'1px solid var(--border-default)'}}>
          <div className="panel-title" style={{marginBottom:8}}>Inspector</div>
          {selNode ? (
            <div className="flex-col gap-xs" style={{fontSize:10}}>
              <div><span className="text-muted">ID:</span> <span className="mono">{selNode.nodeId}</span></div>
              <div><span className="text-muted">Name:</span> <span style={{color:'var(--text-primary)'}}>{selNode.name}</span></div>
              <div><span className="text-muted">Category:</span> {selNode.category}</div>
              <div><span className="text-muted">Provider:</span> {selNode.provider}</div>
              <div><span className="text-muted">Service:</span> {selNode.nativeService||'-'}</div>
              <div><span className="text-muted">Platform:</span> {selNode.platform||'-'}</div>
              <div><span className="text-muted">Security:</span> {selNode.securityZone||'-'}</div>
              <div><span className="text-muted">Data:</span> {selNode.dataClassification||'-'}</div>
              <div><span className="text-muted">Owner:</span> {selNode.owner||'-'}</div>
            </div>
          ) : canonical ? (
            <div className="flex-col gap-xs" style={{fontSize:10}}>
              <div className="text-muted">Select a node to inspect</div>
              <div className="mt-sm"><span className="text-muted">Nodes:</span> <span style={{color:'var(--text-primary)'}}>{canonical.nodes.length}</span></div>
              <div><span className="text-muted">Edges:</span> <span style={{color:'var(--text-primary)'}}>{canonical.edges.length}</span></div>
              <div><span className="text-muted">Provider:</span> {canonical.provider}</div>
              {canonical.nodes.map(n=>(
                <button key={n.nodeId} onClick={()=>setSelNode(n)}
                  style={{textAlign:'left',padding:'3px 6px',borderRadius:3,border:'none',cursor:'pointer',fontSize:9,background:'var(--bg-elevated)',color:'var(--text-secondary)'}}>
                  {n.name}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {/* AI Modal */}
      {showAI && (
        <div className="modal-overlay" onClick={()=>setShowAI(false)}>
          <div className="modal-content" onClick={e=>e.stopPropagation()}>
            <div className="flex-between mb-sm"><div className="panel-title">AI Architecture Generator</div><button className="btn btn-ghost btn-sm" onClick={()=>setShowAI(false)}>×</button></div>
            <div className="badge badge-warning mb-sm" style={{fontSize:10}}>AI_GENERATION_MODE=DETERMINISTIC_POC</div>
            <input className="form-input" placeholder="Business objective" value={aiForm.objective} onChange={e=>setAiForm({...aiForm,objective:e.target.value})}/>
            <input className="form-input" placeholder="Key components" value={aiForm.components} onChange={e=>setAiForm({...aiForm,components:e.target.value})}/>
            <select className="form-select" value={aiForm.provider} onChange={e=>setAiForm({...aiForm,provider:e.target.value})}>
              {['AWS','GCP','ON_PREM','PRIVATE_CLOUD'].map(p=><option key={p} value={p}>{p}</option>)}
            </select>
            <select className="form-select" value={aiForm.platform} onChange={e=>setAiForm({...aiForm,platform:e.target.value})}>
              {['NATIVE_VM','KUBERNETES','OPENSHIFT_OCP','BARE_METAL'].map(p=><option key={p} value={p}>{p}</option>)}
            </select>
            <button className="btn btn-primary" onClick={aiGenerate} style={{width:'100%'}}>Generate Architecture</button>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={()=>setShowCreate(false)}>
          <div className="modal-content" onClick={e=>e.stopPropagation()}>
            <div className="flex-between mb-sm"><div className="panel-title">New Design</div><button className="btn btn-ghost btn-sm" onClick={()=>setShowCreate(false)}>×</button></div>
            <input className="form-input" placeholder="Design name" value={createForm.name} onChange={e=>setCreateForm({...createForm,name:e.target.value})}/>
            <input className="form-input" placeholder="Description" value={createForm.description} onChange={e=>setCreateForm({...createForm,description:e.target.value})}/>
            <select className="form-select" value={createForm.provider} onChange={e=>setCreateForm({...createForm,provider:e.target.value})}>{['AWS','GCP','ON_PREM','PRIVATE_CLOUD'].map(p=><option key={p} value={p}>{p}</option>)}</select>
            <select className="form-select" value={createForm.platform} onChange={e=>setCreateForm({...createForm,platform:e.target.value})}>{['NATIVE_VM','KUBERNETES','OPENSHIFT_OCP','BARE_METAL'].map(p=><option key={p} value={p}>{p}</option>)}</select>
            <button className="btn btn-primary" onClick={createDesign} style={{width:'100%'}}>Create Design</button>
          </div>
        </div>
      )}
      {msg && <div style={{position:'fixed',bottom:16,right:16,zIndex:100,padding:'8px 16px',background:'var(--bg-elevated)',border:'1px solid var(--border-default)',borderRadius:6,fontSize:11,color:'var(--info)',maxWidth:300}} onClick={()=>setMsg('')}>{msg}</div>}
    </div>
  );
}

/* DrawioEmbed component — wraps react-drawio iframe */
function DrawioEmbed({ ref: fwdRef, xml, onSave, onExport, urlParameters, configuration }: any) {
  const [DrawioComp, setDrawioComp] = useState<any>(null);
  const [ready, setReady] = useState(false);

  useEffect(()=>{
    import('react-drawio').then(m=>{
      setDrawioComp(()=>m.DrawIoEmbed);
    }).catch(e=>console.error('Failed to load react-drawio:', e));
  }, []);

  const handleLoad = useCallback((data:any)=>{
    setReady(true);
  }, []);

  if (!DrawioComp) return <div className="loading">Loading draw.io editor...</div>;

  return (
    <DrawioComp
      ref={fwdRef}
      xml={xml}
      autosave={false}
      onSave={onSave}
      onExport={onExport}
      onLoad={handleLoad}
      urlParameters={{
        embed: 1,
        proto: 'json',
        libraries: false,
        noSaveBtn: false,
        noExitBtn: true,
        saveAndExit: false,
        ...urlParameters,
      }}
      configuration={configuration}
      baseUrl="https://embed.diagrams.net"
    />
  );
}
