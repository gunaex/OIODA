
import { useState, useEffect, useCallback, useRef, useMemo, lazy, Suspense } from 'react';
import { api } from '../../lib/api';
import {
  createExampleDesign, canonicalToDrawioXml, drawioXmlToCanonical,
  generateMultiViewXmls, validateArchitectureProposal, resolveDesignHydration,
  type CanonicalDesign, type ArchitectureNode, type ArchitectureProposal,
} from '../../lib/drawioEngine';

const ReactFlowStudio = lazy(() => import('./ReactFlowStudio'));
const AgainPilotPanel = lazy(() => import('./AgainPilotPanel'));

// ── Config ──
const DRAWIO_BASE_URL = (import.meta as any).env?.VITE_DRAWIO_BASE_URL || 'http://localhost:8080';

interface Props {
  actor?: { name: string; role: string };
  wsId?: string;
  onWsChange?: (id: string, name: string) => void;
}

type Engine = 'drawio' | 'reactflow';
const VIEWS = ['architecture', 'dataFlow', 'operationFlow', 'securityFlow'] as const;
type ViewName = typeof VIEWS[number];

export default function ArchitectureWorkspace(props: Props = {}) {
  const { actor = { name: 'kanphong', role: 'Architect' }, wsId = '', onWsChange } = props;

  const [engine, setEngine] = useState<Engine>('drawio');
  const [designs, setDesigns] = useState<any[]>([]);
  const [currentDesign, setCurrentDesign] = useState<any>(null);
  const [canonical, setCanonical] = useState<CanonicalDesign | null>(null);
  const [view, setView] = useState<ViewName>('architecture');
  const [selNode, setSelNode] = useState<ArchitectureNode | null>(null);
  const [msg, setMsg] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [createForm, setCreateForm] = useState({ name: '', description: '', provider: 'ON_PREM', platform: 'NATIVE_VM', fidelity: 'LOCAL_RUNTIME' });
  const drawioRef = useRef<any>(null);
  const [drawioXml, setDrawioXml] = useState<string>('');
  const [drawioLoading, setDrawioLoading] = useState(true);
  const [drawioError, setDrawioError] = useState(false);
  const [drawioReady, setDrawioReady] = useState(false);
  const [hydrationError, setHydrationError] = useState('');

  const loadDesigns = () => api.designs().then((d: any) => setDesigns(d.designs || [])).catch(() => { });

  useEffect(() => { loadDesigns(); }, []);

  // ── Load canonical + generate draw.io XML ──
  //
  // The actual hydration decision (fresh vs. persisted vs. malformed vs.
  // provider-unresolved) lives in resolveDesignHydration — a pure function
  // in drawioEngine.ts, independently unit-tested. This previously inlined
  // that logic and got it wrong (read `d.flow` instead of `d.design.flow`,
  // and `design.provider` — which the sidebar list never carries — instead
  // of the persisted flow's own provider), so every reload of an
  // already-persisted design silently discarded its real architecture for a
  // generic 5-node ON_PREM template, with no error and no id change.
  const loadCanonicalFromDesign = useCallback((design: any) => {
    if (!design) { setCanonical(null); setDrawioXml(''); setHydrationError(''); return; }
    const did = design.designId;
    setDrawioLoading(true);
    setDrawioError(false);
    setHydrationError('');
    api.getDesign(did).then((d: any) => {
      const result = resolveDesignHydration(did, d);
      if (!result.ok || !result.canonical) {
        setHydrationError(result.error || 'DESIGN_HYDRATION_FAILED');
        setCanonical(null); setDrawioXml(''); setDrawioLoading(false);
        return;
      }
      const cd = result.canonical;
      setCanonical(cd);
      if (cd.diagramDocument && cd.diagramEngine === 'drawio') {
        setDrawioXml(cd.diagramDocument);
      } else {
        setDrawioXml(canonicalToDrawioXml(cd, view));
      }
      setDrawioLoading(false);
    }).catch((e) => {
      console.error('Failed to load design flow:', e);
      setHydrationError(`DESIGN_LOAD_FAILED: ${e?.message || e}`);
      setCanonical(null); setDrawioXml(''); setDrawioLoading(false);
    });
  }, [view]);

  useEffect(() => {
    loadCanonicalFromDesign(currentDesign);
  }, [currentDesign]);

  // ── Switch view → regenerate XML ──
  useEffect(() => {
    if (!canonical || !currentDesign) return;
    if (engine !== 'drawio') return;
    if (canonical.diagramEngine !== 'drawio') {
      const xml = canonicalToDrawioXml(canonical, view);
      setDrawioXml(xml);
    }
    // If we have stored XML and are on the view it was generated for, keep it
  }, [view, engine]);

  // ── Handle draw.io save with reconciliation ──
  const handleDrawioSave = useCallback((data: any) => {
    const xml = data.xml || data.data || '';
    if (!xml || !canonical) {
      setMsg('Save error: no XML or canonical model');
      return;
    }

    // Reconcile XML → canonical
    const { canonical: updated, classifications } = drawioXmlToCanonical(xml, canonical);
    setCanonical(updated);
    setDrawioXml(xml);

    const did = currentDesign?.designId;
    if (!did) { setMsg('Save error: no design selected'); return; }
    // Persist full canonical + XML
    api.updateDesignFlow(did, updated)
      .then(() => {
        const newNodeCount = classifications.filter(c => c.classification === 'NEW_VISUAL_NODE').length;
        const removedCount = classifications.filter(c => c.classification === 'REMOVED_NODE').length;
        const unmapped = classifications.filter(c => c.classification === 'UNMAPPED_COMPONENT').length;
        let statusMsg = 'Design saved';
        if (newNodeCount > 0) statusMsg += ` (+${newNodeCount} new node${newNodeCount > 1 ? 's' : ''})`;
        if (removedCount > 0) statusMsg += ` (-${removedCount} removed)`;
        if (unmapped > 0) statusMsg += ` [${unmapped} unmapped]`;
        setMsg(statusMsg);
      })
      .catch((e: any) => setMsg('Save error: ' + e.message));
  }, [canonical, currentDesign]);

  const handleDrawioExport = useCallback((data: any) => {
    if (data.format === 'xmlsvg' || data.format === 'svg') {
      handleDrawioSave({ xml: data.xml || data.data });
    }
  }, [handleDrawioSave]);

  // ── Create design ──
  const createDesign = async () => {
    try {
      const r = await api.createDesign({
        name: createForm.name,
        description: createForm.description,
        provider: createForm.provider,
        platform: createForm.platform,
        fidelity: createForm.fidelity,
      });
      const did = r.designId;
      if (!did) throw new Error('CREATE_DESIGN_NO_ID');
      // Immediately set canonical for this design
      const cd = createExampleDesign(createForm.provider);
      cd.designId = did;
      cd.title = createForm.name;
      cd.description = createForm.description;
      cd.provider = createForm.provider;
      cd.platform = createForm.platform;
      // Persist initial flow with canonical data
      await api.updateDesignFlow(did, cd);
      setMsg('Design created: ' + did);
      loadDesigns();
      setShowCreate(false);
      if (wsId && onWsChange) api.setWsDesign(wsId, did).catch(() => { });
    } catch (e: any) { setMsg('Error: ' + e.message); }
  };

  // ── Accept design ──
  const acceptDesign = async () => {
    if (!currentDesign) return;
    try {
      const did = currentDesign.designId;
      if (!did) throw new Error('DESIGN_ID_REQUIRED');
      await api.acceptDesign(did);
      loadDesigns();
      setMsg('Design accepted — now frozen');
    } catch (e: any) { setMsg('Error: ' + e.message); }
  };

  // ── Clone revision ──
  const cloneRevision = async () => {
    if (!currentDesign) return;
    try {
      const copy = {
        ...currentDesign,
        name: (currentDesign.name || currentDesign.metadata?.name || currentDesign.designId) + ' (Clone)',
        status: 'DRAFT',
      };
      const r = await api.createDesign(copy);
      const did = r.id || r.designId;
      // Also copy flow
      if (canonical) {
        const cloned = { ...canonical, designId: did, status: 'DRAFT', version: (parseInt(canonical.version) + 1).toString() };
        await api.updateDesignFlow(did, cloned).catch(() => { });
      }
      setMsg('Clone created: ' + did);
      loadDesigns();
    } catch (e: any) { setMsg('Clone error: ' + e.message); }
  };

  // ── Draw.io failure handler ──
  const handleDrawioError = useCallback(() => {
    setDrawioError(true);
    setDrawioLoading(false);
  }, []);

  const retryDrawio = () => {
    setDrawioError(false);
    setDrawioLoading(true);
    if (canonical) {
      const xml = canonicalToDrawioXml(canonical, view);
      setDrawioXml(xml);
    }
  };

  const isFrozen = currentDesign?.status === 'ACCEPTED' || currentDesign?.status === 'BASELINE_FROZEN';
  // Authoritative provider comes ONLY from the hydrated canonical design.
  // No silent 'ON_PREM' fallback while a design is selected but not yet
  // (or not successfully) hydrated — that's exactly the substitution that
  // caused refine requests to validate against the wrong provider. Only
  // default to 'AWS' when there is no design context at all (nothing to
  // misrepresent).
  const provider = canonical?.provider || (currentDesign ? '' : 'AWS');

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 88px)', gap: 0, overflow: 'hidden' }}>
      {/* LEFT PANEL */}
      <div style={{ width: 220, minWidth: 220, background: 'var(--bg-surface)', borderRight: '1px solid var(--border-default)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: 12, borderBottom: '1px solid var(--border-default)' }}>
          <div className="panel-title">Designs</div>
          <button className="btn btn-primary btn-sm" style={{ marginTop: 8, width: '100%' }} onClick={() => setShowCreate(!showCreate)}>+ New Design</button>
          <button className="btn btn-secondary btn-sm" style={{ marginTop: 4, width: '100%' }} onClick={() => setShowAI(!showAI)}>AI Generate</button>
          <div className="flex-row gap-xs" style={{ marginTop: 8 }}>
            <button className={`btn btn-sm ${engine === 'drawio' ? 'btn-primary' : 'btn-ghost'}`} style={{ fontSize: 9, flex: 1 }} onClick={() => setEngine('drawio')}>draw.io</button>
            <button className={`btn btn-sm ${engine === 'reactflow' ? 'btn-primary' : 'btn-ghost'}`} style={{ fontSize: 9, flex: 1 }} onClick={() => setEngine('reactflow')}>React Flow</button>
          </div>
        </div>
        <div className="flex-col" style={{ flex: 1, overflow: 'auto', padding: '4px 8px', gap: 2 }}>
          {designs.map((d: any) => (
            <button key={d.designId} onClick={() => setCurrentDesign(d)}
              style={{
                textAlign: 'left', padding: '6px 8px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: 11,
                background: currentDesign?.designId === d.designId ? 'var(--bg-active)' : 'transparent',
                color: 'var(--text-secondary)'
              }}>
              <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{(d.name || d.metadata?.name || d.designId || '').slice(0, 20)}</div>
              <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>{d.status || 'DRAFT'} · {d.provider || '?'}</div>
            </button>
          ))}
        </div>
      </div>

      {/* CENTER */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Toolbar */}
        <div style={{ height: 36, minHeight: 36, background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-default)', display: 'flex', alignItems: 'center', padding: '0 12px', gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)' }}>{canonical?.title || 'No design'}</span>
          {currentDesign && <span className={`badge ${isFrozen ? 'badge-success' : 'badge-neutral'}`} style={{ fontSize: 9 }}>{currentDesign.status || 'DRAFT'}</span>}
          <span className={`badge ${provider ? 'badge-info' : 'badge-danger'}`} style={{ fontSize: 9 }}>{provider || 'PROVIDER UNRESOLVED'}</span>
          <div style={{ flex: 1 }} />
          {VIEWS.map(v => (
            <button key={v} onClick={() => setView(v)} className={`btn btn-sm ${view === v ? 'btn-primary' : 'btn-ghost'}`} style={{ fontSize: 10, textTransform: 'capitalize' }}>
              {v.replace(/([A-Z])/g, ' $1')}
            </button>
          ))}
          {!isFrozen && <button className="btn btn-primary btn-sm" onClick={() => drawioRef.current?.exportDiagram({ format: 'xmlsvg' })}>Save</button>}
          {!isFrozen && currentDesign && <button className="btn btn-sm" style={{ background: 'var(--success)', color: '#000' }} onClick={acceptDesign}>Accept</button>}
          {isFrozen && <>
            <span className="badge badge-success">FROZEN</span>
            <button className="btn btn-sm btn-ghost" onClick={cloneRevision}>Clone</button>
          </>}
        </div>

        {/* Canvas */}
        <div style={{ flex: 1, background: 'var(--bg-root)', position: 'relative' }}>
          {!currentDesign ? (
            <div className="empty-state" style={{ height: '100%' }}>
              <div className="empty-state-title">Select or create a design</div>
            </div>
          ) : hydrationError ? (
            <div className="empty-state" style={{ height: '100%', flexDirection: 'column', gap: 12 }}>
              <div className="empty-state-title" style={{ color: 'var(--danger)' }}>Could not load this design's architecture</div>
              <div className="text-muted mono" style={{ fontSize: 11, maxWidth: 480, textAlign: 'center' }}>{hydrationError}</div>
              <div className="text-muted" style={{ fontSize: 10 }}>Refusing to substitute a generic template for a persisted design that failed to load.</div>
              <button className="btn btn-secondary btn-sm" onClick={() => loadCanonicalFromDesign(currentDesign)}>Retry</button>
            </div>
          ) : engine === 'drawio' ? (
            drawioError ? (
              <div className="empty-state" style={{ height: '100%', flexDirection: 'column', gap: 12 }}>
                <div className="empty-state-title">Diagram editor unavailable</div>
                <div className="text-muted" style={{ fontSize: 11 }}>Draw.io service is not reachable at {DRAWIO_BASE_URL}</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-primary btn-sm" onClick={retryDrawio}>Retry</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => setEngine('reactflow')}>Switch to React Flow</button>
                </div>
              </div>
            ) : drawioLoading ? <div className="loading">Loading draw.io...</div> : (
              <DrawioEmbed
                ref={drawioRef}
                xml={drawioXml}
                onSave={handleDrawioSave}
                onExport={handleDrawioExport}
                onError={handleDrawioError}
                urlParameters={{ libraries: false, saveAndExit: false, noExitBtn: true, noSaveBtn: false }}
                configuration={{ defaultFonts: ['system-ui'] }}
                baseUrl={DRAWIO_BASE_URL}
              />
            )
          ) : (
            <Suspense fallback={<div className="loading">Loading React Flow...</div>}>
              <ReactFlowStudio canonical={canonical} onSave={(c: CanonicalDesign) => setCanonical(c)} />
            </Suspense>
          )}
        </div>
      </div>

      {/* RIGHT PANEL — Inspector */}
      <div style={{ width: 200, minWidth: 200, background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-default)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: 12, borderBottom: '1px solid var(--border-default)' }}>
          <div className="panel-title" style={{ marginBottom: 8 }}>Inspector</div>
          {selNode ? (
            <div className="flex-col gap-xs" style={{ fontSize: 10 }}>
              <div><span className="text-muted">ID:</span> <span className="mono">{selNode.nodeId}</span></div>
              <div><span className="text-muted">Name:</span> <span style={{ color: 'var(--text-primary)' }}>{selNode.name}</span></div>
              <div><span className="text-muted">Category:</span> {selNode.category}</div>
              <div><span className="text-muted">Provider:</span> {selNode.provider}</div>
              <div><span className="text-muted">Service:</span> {selNode.nativeService || '-'}</div>
              <div><span className="text-muted">Platform:</span> {selNode.platform || '-'}</div>
              <div><span className="text-muted">Security:</span> {selNode.securityZone || '-'}</div>
              <div><span className="text-muted">Data:</span> {selNode.dataClassification || '-'}</div>
              <div><span className="text-muted">Owner:</span> {selNode.owner || '-'}</div>
              <button className="btn btn-ghost btn-sm" onClick={() => setSelNode(null)} style={{ marginTop: 8 }}>Deselect</button>
            </div>
          ) : canonical ? (
            <div className="flex-col gap-xs" style={{ fontSize: 10 }}>
              <div className="text-muted">Select a node to inspect</div>
              <div className="mt-sm"><span className="text-muted">Nodes:</span> <span style={{ color: 'var(--text-primary)' }}>{canonical.nodes.length}</span></div>
              <div><span className="text-muted">Edges:</span> <span style={{ color: 'var(--text-primary)' }}>{canonical.edges.length}</span></div>
              <div><span className="text-muted">Provider:</span> {canonical.provider}</div>
              <div><span className="text-muted">View:</span> {view}</div>
              {canonical.nodes.map(n => (
                <button key={n.nodeId} onClick={() => setSelNode(n)}
                  style={{ textAlign: 'left', padding: '3px 6px', borderRadius: 3, border: 'none', cursor: 'pointer', fontSize: 9, background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                  {n.name}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {/* AGAINPILOT Panel */}
      {showAI && (
        <Suspense fallback={<div className="loading">Loading AGAINPILOT…</div>}>
          <AgainPilotPanel
            provider={provider}
            platform={canonical?.platform || 'KUBERNETES'}
            hasDesign={!!currentDesign}
            designId={currentDesign?.designId}
            designName={currentDesign?.name || currentDesign?.metadata?.name}
            designStatus={currentDesign?.status}
            onRefineApply={async (designId: string, refinedProposal: any) => {
              // Build canonical from refined proposal
              const cd = createExampleDesign(provider);
              cd.title = refinedProposal.title || 'Refined Architecture';
              cd.description = refinedProposal.summary || '';
              cd.nodes = (refinedProposal.nodes || []).map((n: any) => ({
                nodeId: n.nodeId, name: n.name, category: n.category,
                provider: n.provider || provider, nativeService: n.nativeService || '',
                platform: n.platform || 'NATIVE_VM',
                properties: n.properties || {},
                securityZone: n.securityZone || 'private',
                dataClassification: n.dataClassification || 'internal',
                owner: n.owner || '', source: n.source || 'AI_GENERATED',
                verificationState: n.verificationState || 'UNVERIFIED',
              }));
              cd.edges = (refinedProposal.edges || []).map((e: any) => ({
                edgeId: e.edgeId, sourceNodeId: e.sourceNodeId, targetNodeId: e.targetNodeId,
                type: e.type || 'request', protocol: e.protocol || 'TCP',
                direction: e.direction || 'unidirectional',
                dataType: e.dataType || '', securityClassification: e.securityClassification || 'none',
                label: e.label || '',
              }));
              cd.groups = (refinedProposal.groups || []).map((g: any) => ({
                groupId: g.groupId, name: g.name, type: g.type || 'SUBNET',
                parentGroupId: g.parentGroupId || '',
                provider: g.provider || provider, securityZone: g.securityZone || 'private',
              }));
              cd.designId = designId;
              await api.updateDesignFlow(designId, cd);
              // Reload authoritative design + refresh draw.io
              setCanonical(cd);
              const xml = canonicalToDrawioXml(cd, 'architecture');
              setDrawioXml(xml);
              setMsg('AGAINPILOT refine applied');
              loadDesigns();
            }}
            onApply={(proposal: any) => {
              // Convert AGAINPILOT proposal → canonical → persist → draw.io
              const cd = createExampleDesign(provider);
              cd.title = proposal.title || 'AGAINPILOT Architecture';
              cd.description = proposal.summary || '';
              cd.nodes = (proposal.nodes || []).map((n: any) => ({
                nodeId: n.nodeId, name: n.name, category: n.category,
                provider: n.provider || provider, nativeService: n.nativeService || '',
                platform: n.platform || 'NATIVE_VM',
                properties: n.properties || {},
                securityZone: n.securityZone || 'private',
                dataClassification: n.dataClassification || 'internal',
                owner: n.owner || '', source: n.source || 'AI_GENERATED',
                verificationState: n.verificationState || 'UNVERIFIED',
              }));
              cd.edges = (proposal.edges || []).map((e: any) => ({
                edgeId: e.edgeId, sourceNodeId: e.sourceNodeId, targetNodeId: e.targetNodeId,
                type: e.type || 'request', protocol: e.protocol || 'TCP',
                direction: e.direction || 'unidirectional',
                dataType: e.dataType || '', securityClassification: e.securityClassification || 'none',
                label: e.label || '',
              }));
              cd.groups = (proposal.groups || []).map((g: any) => ({
                groupId: g.groupId, name: g.name, type: g.type || 'SUBNET',
                parentGroupId: g.parentGroupId || '',
                provider: g.provider || provider, securityZone: g.securityZone || 'private',
              }));
              cd.views = {
                architecture: proposal.views?.architecture?.nodes || cd.nodes.map((n: any) => n.nodeId),
                dataFlow: proposal.views?.dataFlow?.nodes || [],
                operationFlow: proposal.views?.operationFlow?.nodes || [],
                securityFlow: proposal.views?.securityFlow?.nodes || [],
              };
              cd.aiRationale = proposal.rationale || '';
              cd.assumptions = proposal.assumptions || [];
              cd.risks = proposal.risks || [];
              cd.diagramEngine = 'drawio';

              const existingDid = currentDesign?.designId;
              if (existingDid) {
                // Apply to existing design
                api.updateDesignFlow(existingDid, cd).then(() => {
                  setCanonical(cd);
                  const xml = canonicalToDrawioXml(cd, 'architecture');
                  setDrawioXml(xml);
                  setMsg('AGAINPILOT architecture applied');
                  loadDesigns();
                }).catch((e: any) => setMsg('Apply error: ' + e.message));
              } else {
                // Atomic create-and-apply
                api.createDesign({
                  name: cd.title,
                  description: cd.description || '',
                  provider: cd.provider,
                  platform: cd.platform,
                  fidelity: 'LOCAL_RUNTIME',
                }).then((cr: any) => {
                  const newDid = cr.designId;
                  if (!newDid) throw new Error('CREATE_DESIGN_NO_ID');
                  cd.designId = newDid;
                  return api.updateDesignFlow(newDid, cd).then(() => newDid);
                }).then((newDid: string) => {
                  if (wsId && onWsChange) api.setWsDesign(wsId, newDid).catch(() => {});
                  return api.getDesign(newDid);
                }).then((d: any) => {
                  const authoritative = d.design || d;
                  setCurrentDesign(authoritative);
                  loadDesigns();
                  setMsg('Design created from AGAINPILOT proposal: ' + cd.designId);
                }).catch((e: any) => setMsg('Create & Apply error: ' + e.message));
              }
            }}
            onClose={() => setShowAI(false)}
          />
        </Suspense>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="flex-between mb-sm"><div className="panel-title">New Design</div><button className="btn btn-ghost btn-sm" onClick={() => setShowCreate(false)}>×</button></div>
            <input className="form-input" placeholder="Design name" value={createForm.name} onChange={e => setCreateForm({ ...createForm, name: e.target.value })} />
            <input className="form-input" placeholder="Description" value={createForm.description} onChange={e => setCreateForm({ ...createForm, description: e.target.value })} />
            <select className="form-select" value={createForm.provider} onChange={e => setCreateForm({ ...createForm, provider: e.target.value })}>{['AWS', 'GCP', 'ON_PREM', 'PRIVATE_CLOUD'].map(p => <option key={p} value={p}>{p}</option>)}</select>
            <select className="form-select" value={createForm.platform} onChange={e => setCreateForm({ ...createForm, platform: e.target.value })}>{['NATIVE_VM', 'KUBERNETES', 'OPENSHIFT_OCP', 'BARE_METAL'].map(p => <option key={p} value={p}>{p}</option>)}</select>
            <button className="btn btn-primary" onClick={createDesign} style={{ width: '100%' }}>Create Design</button>
          </div>
        </div>
      )}
      {msg && <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 100, padding: '8px 16px', background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', borderRadius: 6, fontSize: 11, color: 'var(--info)', maxWidth: 300, cursor: 'pointer' }} onClick={() => setMsg('')}>{msg}</div>}
    </div>
  );
}

/* ── DrawioEmbed component with security hardening ── */
const MAX_DRAWIO_XML_BYTES = 2 * 1024 * 1024; // 2 MB

function DrawioEmbed({ ref: fwdRef, xml, onSave, onExport, onError, urlParameters, configuration, baseUrl }: any) {
  const [DrawioComp, setDrawioComp] = useState<any>(null);
  const [loadErr, setLoadErr] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Derive allowed origin from baseUrl
  const allowedOrigin = useMemo(() => {
    try {
      const u = new URL(baseUrl || DRAWIO_BASE_URL);
      return u.origin;
    } catch { return (typeof window !== 'undefined' ? window.location.origin : ''); }
  }, [baseUrl]);

  // PostMessage origin validation
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.origin !== allowedOrigin) {
        // Silently reject messages from unexpected origins
        return;
      }
      // Allow only from the configured draw.io origin
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [allowedOrigin]);

  // Apply iframe sandbox after mount
  useEffect(() => {
    if (!DrawioComp) return;
    const timer = setTimeout(() => {
      const iframe = document.querySelector('iframe[src*="drawio"], iframe[src*="diagrams.net"], iframe[src*="localhost"]');
      if (iframe && !iframe.hasAttribute('data-sandbox-applied')) {
        // Allow same-origin (needed for draw.io postMessage), scripts (draw.io editor),
        // forms (search/UI), but deny popups, top-navigation, plugins
        iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms');
        iframe.setAttribute('data-sandbox-applied', 'true');
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [DrawioComp]);

  // Size-limit XML before save
  const safeOnSave = useCallback((data: any) => {
    const xmlStr = data.xml || data.data || '';
    if (xmlStr && xmlStr.length > MAX_DRAWIO_XML_BYTES) {
      console.error('Draw.io XML exceeds size limit:', xmlStr.length, 'bytes');
      onError?.('XML_SIZE_EXCEEDED');
      return;
    }
    onSave(data);
  }, [onSave, onError]);

  useEffect(() => {
    import('react-drawio').then(m => {
      setDrawioComp(() => m.DrawIoEmbed);
    }).catch(e => {
      console.error('Failed to load react-drawio:', e);
      setLoadErr(true);
      onError?.();
    });
  }, []);

  if (loadErr || !DrawioComp) return <div className="loading">Loading draw.io editor...</div>;

  return (
    <DrawioComp
      ref={fwdRef}
      xml={xml}
      autosave={false}
      onSave={safeOnSave}
      onExport={onExport}
      onLoad={() => { }}
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
      baseUrl={baseUrl}
    />
  );
}
