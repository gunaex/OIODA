
import { useState, Suspense, lazy, createContext, useContext, useEffect } from 'react';

// ── Actor Context ──
interface Actor { name: string; role: string; }
const ROLES = ['Architect','Planner','Executor','Observer','Validator','Verifier','Approver','UAT Performer'];
const STORAGE_KEY = 'infra-again-actor';
function loadActor(): Actor {
  try { const d=JSON.parse(localStorage.getItem(STORAGE_KEY)||''); if(d?.name) return d; } catch {}
  return { name:'kanphong', role:'Architect' };
}
export const ActorCtx = createContext<{actor:Actor;setActor:(a:Actor)=>void}>({actor:loadActor(),setActor:()=>{}});

const FlightDeck = lazy(() => import('./features/flight-deck/FlightDeck'));
const ArchitectureWorkspace = lazy(() => import('./features/workspaces/ArchitectureWorkspace'));
const ImplementationWorkspace = lazy(() => import('./features/workspaces/ImplementationWorkspace'));
const ExecutionCenter = lazy(() => import('./features/workspaces/ExecutionCenter'));
const EvidenceViewer = lazy(() => import('./features/workspaces/EvidenceViewer'));
const PromotionCenter = lazy(() => import('./features/workspaces/PromotionCenter'));
const RecoveryCenter = lazy(() => import('./features/workspaces/RecoveryCenter'));
const UatWorkspace = lazy(() => import('./features/workspaces/UatWorkspace'));
const ProductionReadiness = lazy(() => import('./features/workspaces/ProductionReadiness'));
const ProviderIntelligence = lazy(() => import('./features/workspaces/ProviderIntelligence'));
const SystemSafety = lazy(() => import('./features/workspaces/SystemSafety'));

type View = 'flight-deck'|'architecture'|'implementation'|'execution'|'evidence'|'promotion'|'recovery'|'uat'|'prod-readiness'|'providers'|'system';
const NAV: {id:View;label:string;icon:string}[]=[
  {id:'flight-deck',label:'Flight Deck',icon:'\u25c8'},
  {id:'architecture',label:'Architecture',icon:'\u25c7'},
  {id:'implementation',label:'Implementation',icon:'\u25a3'},
  {id:'execution',label:'Execution',icon:'\u25b6'},
  {id:'evidence',label:'Evidence',icon:'\u2637'},
  {id:'promotion',label:'Promotion',icon:'\u2197'},
  {id:'recovery',label:'Recovery',icon:'\u21ba'},
  {id:'uat',label:'UAT',icon:'\u2713'},
  {id:'prod-readiness',label:'Prod Readiness',icon:'\u25c6'},
  {id:'providers',label:'Providers',icon:'\u2b21'},
  {id:'system',label:'System',icon:'\u2699'},
];

function Loading(){ return <div className="loading">Loading\u2026</div>; }

export default function App() {
  const [view,setView]=useState<View>('flight-deck');
  const [actor,setActorState]=useState<Actor>(loadActor());
  const setActor=(a:Actor)=>{ setActorState(a); localStorage.setItem(STORAGE_KEY,JSON.stringify(a)); };
  const [wsId,setWsId]=useState<string>('');
  const [wsName,setWsName]=useState('No active workspace');

  const page = ()=>(
    <Suspense fallback={<Loading/>}>
      {view==='flight-deck'&&<FlightDeck onNavigate={setView} wsId={wsId} wsName={wsName} onWsChange={(id:string,n:string)=>{setWsId(id);setWsName(n||'Workspace');}}/>}
      {view==='architecture'&&<ArchitectureWorkspace actor={actor} wsId={wsId} onWsChange={(id:string,n:string)=>{setWsId(id);setWsName(n||'Workspace');}}/>}
      {view==='implementation'&&<ImplementationWorkspace actor={actor} wsId={wsId}/>}
      {view==='execution'&&<ExecutionCenter actor={actor} wsId={wsId}/>}
      {view==='evidence'&&<EvidenceViewer wsId={wsId}/>}
      {view==='promotion'&&<PromotionCenter actor={actor} wsId={wsId}/>}
      {view==='recovery'&&<RecoveryCenter actor={actor} wsId={wsId}/>}
      {view==='uat'&&<UatWorkspace actor={actor} wsId={wsId}/>}
      {view==='prod-readiness'&&<ProductionReadiness actor={actor} wsId={wsId}/>}
      {view==='providers'&&<ProviderIntelligence/>}
      {view==='system'&&<SystemSafety/>}
    </Suspense>
  );

  return (
    <ActorCtx.Provider value={{actor,setActor}}>
      <div className="app-shell">
        <nav className="nav-rail">
          <div className="nav-rail-logo">IA</div>
          {NAV.map(n=>(
            <button key={n.id} onClick={()=>setView(n.id)} title={n.label}
              className={`nav-item${view===n.id?' active':''}`}>{n.icon}</button>
          ))}
        </nav>
        <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',minWidth:0}}>
          <header className="topbar">
            <span className="topbar-brand">INFRA-AGAIN</span>
            <span className="topbar-sep">|</span>
            <span className="topbar-page">{NAV.find(n=>n.id===view)?.label||'Flight Deck'}</span>
            <span className="topbar-workspace">{wsName}</span>
            <div className="topbar-spacer"/>
            <span className="badge badge-warning">SANDBOX: ASK</span>
            <span className="badge badge-danger">CR: BLOCK</span>
            <span className="badge badge-danger">PROD: BLOCK</span>
            <select value={actor.name+':'+actor.role} onChange={e=>{const[n,r]=e.target.value.split(':');setActor({name:n,role:r});}}
              className="form-select" style={{width:'auto',marginBottom:0,fontSize:10,padding:'3px 6px'}}>
              {ROLES.map(r=><option key={r} value={actor.name+':'+r}>{actor.name} · {r}</option>)}
            </select>
          </header>
          <main className="workspace">{page()}</main>
        </div>
      </div>
    </ActorCtx.Provider>
  );
}
