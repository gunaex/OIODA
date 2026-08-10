
const BASE = (import.meta as any).env?.VITE_API_URL ?? '';
async function req<T=any>(path:string,opts?:RequestInit):Promise<T>{
  const res=await fetch(`${BASE}${path}`,{headers:{'Content-Type':'application/json',...opts?.headers},...opts});
  if(!res.ok){const b=await res.text().catch(()=>'');throw new Error(`HTTP ${res.status}: ${b.slice(0,300)}`);}
  return res.json();
}

// ── ID guards ──
function assertResourceId(id: string | undefined | null, type: string): string {
  if (!id || id === 'undefined' || id === 'null') {
    throw new Error(`${type.toUpperCase()}_ID_REQUIRED`);
  }
  return id;
}

// ── Design response normalization ──
function normalizeDesignId(response: any): string {
  const id = response?.design?.designId ?? response?.designId ?? response?.id;
  if (!id) throw new Error('CREATE_DESIGN_NO_ID');
  return id;
}

export const api={
  get:<T=any>(p:string)=>req<T>(p),
  post:<T=any>(p:string,d?:unknown)=>req<T>(p,{method:'POST',body:d?JSON.stringify(d):undefined}),
  // Workspace
  workspaces:()=>api.get<{workspaces:any[]}>('/api/v1/workspaces'),
  createWorkspace:(b:any)=>api.post('/api/v1/workspaces',b),
  getWorkspace:(id:string)=>api.get<{workspace:any}>(`/api/v1/workspaces/${id}`),
  setWsDesign:(id:string,designId:string)=>api.post(`/api/v1/workspaces/${id}/current-design?design_id=${encodeURIComponent(assertResourceId(designId,'design'))}`),
  setWsPlan:(id:string,planId:string)=>api.post(`/api/v1/workspaces/${id}/current-plan?plan_id=${encodeURIComponent(assertResourceId(planId,'plan'))}`),
  setWsPackage:(id:string,pkgId:string)=>api.post(`/api/v1/workspaces/${id}/current-package?package_id=${encodeURIComponent(assertResourceId(pkgId,'package'))}`),
  // Designs — normalized responses
  designs:()=>api.get<{designs:any[]}>('/api/v1/designs'),
  createDesign: async (b:any) => {
    const r = await api.post('/api/v1/designs',b);
    return { designId: normalizeDesignId(r), ...r };
  },
  getDesign: (id:string) => api.get<any>(`/api/v1/designs/${assertResourceId(id,'design')}`),
  acceptDesign: (id:string) => api.post(`/api/v1/designs/${assertResourceId(id,'design')}/accept`),
  aiGenerate: (id:string,b:any) => api.post(`/api/v1/designs/${assertResourceId(id,'design')}/ai-generate`,b),
  updateDesignFlow: (id:string,flow:any) => api.post(`/api/v1/designs/${assertResourceId(id,'design')}/update-flow`,{flow}),
  // AGAINPILOT
  againpilotStatus:()=>api.get<{mode:string;provider:string;available:boolean}>('/api/v1/againpilot/status'),
  againpilotGenerate:(b:any)=>api.post<{proposal:any}>('/api/v1/againpilot/generate',b),
  againpilotRefine:(b:any)=>api.post<{proposal:any;delta:any}>('/api/v1/againpilot/refine',b),
  againpilotExplain:(b:any)=>api.post<{explanation:string}>('/api/v1/againpilot/explain',b),
  againpilotSecurity:(b:any)=>api.post<{analysis:any}>('/api/v1/againpilot/security-analysis',b),
  // Plans
  createPlan:(designId:string)=>api.post(`/api/v1/designs/${designId}/implementation-plan`),
  getPlan:(id:string)=>api.get<any>(`/api/v1/implementation-plans/${id}`),
  approvePlan:(id:string)=>api.post(`/api/v1/implementation-plans/${id}/approve`),
  rejectPlan:(id:string)=>api.post(`/api/v1/implementation-plans/${id}/request-change`),
  // Execution
  getReadiness:(planId:string)=>api.post(`/api/v1/implementation-plans/${planId}/execution-readiness`),
  createPackage:(planId:string,b?:any)=>api.post(`/api/v1/implementation-plans/${planId}/execution-packages`,b),
  getPackage:(id:string)=>api.get<any>(`/api/v1/execution-packages/${id}`),
  preflight:(pkgId:string)=>api.post(`/api/v1/execution-packages/${pkgId}/preflight`),
  execute:(pkgId:string)=>api.post(`/api/v1/execution-packages/${pkgId}/execute`),
  getRun:(id:string)=>api.get<any>(`/api/v1/execution-runs/${id}`),
  getRunEvidence:(id:string)=>api.get<any>(`/api/v1/execution-runs/${id}/evidence`),
  // Promotions
  promotions:()=>api.get<{promotions:any[]}>('/api/v1/promotions'),
  createPromotion:(b:any)=>api.post('/api/v1/promotions',b),
  getPromotion:(id:string)=>api.get<{promotion:any}>(`/api/v1/promotions/${id}`),
  approvePromotion:(id:string,by:string)=>api.post(`/api/v1/promotions/${id}/approve?approved_by=${encodeURIComponent(by)}`),
  rejectPromotion:(id:string)=>api.post(`/api/v1/promotions/${id}/reject`),
  consumePromotion:(id:string)=>api.post(`/api/v1/promotions/${id}/consume`),
  // Rollback
  rollbacks:()=>api.get<{rollbackPlans:any[]}>('/api/v1/rollback-plans'),
  createRollback:(b:any)=>api.post('/api/v1/rollback-plans',b),
  approveRollback:(id:string,by:string)=>api.post(`/api/v1/rollback-plans/${id}/approve?approved_by=${encodeURIComponent(by)}`),
  // UAT
  uats:()=>api.get<{uats:any[]}>('/api/v1/uat'),
  createUat:(b:any)=>api.post('/api/v1/uat',b),
  passUat:(id:string,performedBy:string,approvedBy:string)=>api.post(`/api/v1/uat/${id}/pass?performed_by=${encodeURIComponent(performedBy)}&approved_by=${encodeURIComponent(approvedBy)}`),
  failUat:(id:string)=>api.post(`/api/v1/uat/${id}/fail`),
  // Readiness
  evaluateReadiness:(b:any)=>api.post('/api/v1/production-readiness/evaluate',b),
  readinessList:()=>api.get<{readinessRecords:any[]}>('/api/v1/production-readiness'),
  // Environments
  environments:()=>api.get<{environments:any[]}>('/api/v1/environments'),
  // Runs
  runs:()=>api.get<{runs:any[]}>('/api/v1/runs'),
};
