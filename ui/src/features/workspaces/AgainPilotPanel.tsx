/* AGAINPILOT — AI Architecture Copilot Panel.
   Natural language → Canonical Architecture → draw.io.
   R.9: Added Refine mode with design context, change preview, apply/cancel. */
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

interface Props {
  provider: string;
  platform: string;
  hasDesign: boolean;
  designId?: string;
  designName?: string;
  designStatus?: string;
  onApply: (proposal: any, delta?: any) => void;
  onRefineApply?: (designId: string, proposal: any) => Promise<void>;
  onClose: () => void;
}

const EXAMPLES = [
  { title: 'Patient Portal',
    brief: `Build a patient portal on AWS for 10,000 users/day.\nUse private database access, containerized workloads,\nhigh availability and PDPA-aligned security.`, },
  { title: 'Enterprise Internal App',
    brief: `Build an internal enterprise web application on-premise\nusing Kubernetes, PostgreSQL, private networking,\nSSO and highly available application services.`, },
  { title: 'Data Platform',
    brief: `Design a cloud data platform that receives batch and streaming data,\nstores raw and curated datasets, provides analytics,\nand separates public ingress from private data services.`, },
];

const REFINE_EXAMPLES = [
  'Use ECS Fargate for the application tier',
  'Move the database to a private data tier',
  'Add Redis cache between application and database',
  'Add SQS for asynchronous processing',
];

type Stage = 'input' | 'generating' | 'review' | 'fallback'
  | 'refine-input' | 'refining' | 'refine-preview' | 'refine-applying' | 'refine-applied' | 'refine-failed' | 'refine-fallback';

// ── Hybrid/cloud execution path — M4-D.1 ──
// Renders only when provenance.requestPolicy is present, i.e. the M3 hybrid
// router actually ran (local-only / deterministic-fallback provenance has no
// requestPolicy field, so the existing plain badges below are untouched).
// Never shown: raw model text, chain-of-thought, reasoning_content — only
// the structured routing fields the backend provenance contract exposes.
const RESULT_LABELS: Record<string, string> = {
  QUALITY_GATE_FAILED: 'Quality Failed', COMPLETENESS_GATE_FAILED: 'Completeness Failed',
  LOCAL_MODEL_UNAVAILABLE: 'Local Unavailable', CORRECTION_FAILED: 'Correction Failed',
  LOCAL_TIMEOUT: 'Local Timeout', SKIPPED_COMPLEX_REFINE: 'Skipped (complex refine)',
  LOCAL_ACCEPTED: 'Accepted', LOCAL_CORRECTED: 'Accepted (corrected)',
  CLOUD_ESCALATED: 'Accepted', CLOUD_DIRECT: 'Accepted',
  BLOCKED: 'Blocked', NEEDS_USER_REVIEW: 'Needs Review',
};
const humanize = (code?: string) => (code ? (RESULT_LABELS[code] || code) : '');

function ExecutionPathView({ provenance }: { provenance: any }) {
  if (!provenance?.requestPolicy) return null;
  const steps: string[] = [];
  if (provenance.localModel) {
    steps.push(`Local · ${provenance.localModel}`);
    if (provenance.escalated && provenance.localResult) steps.push(humanize(provenance.localResult));
  }
  if (provenance.cloudProvider) {
    steps.push(`Cloud Expert · ${provenance.cloudProvider}${provenance.cloudModel ? ' ' + provenance.cloudModel : ''}`);
  }
  const finalLabel = humanize(provenance.finalResultMode);
  if (finalLabel) steps.push(finalLabel);

  return (
    <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 6, lineHeight: 1.6 }}>
      <div>Policy: <span className="mono">{provenance.requestPolicy}</span></div>
      <div>Execution Path: {steps.join(' → ')}</div>
      {typeof provenance.cloudLatencyMs === 'number' && provenance.cloudProvider && (
        <div>Cloud latency: {(provenance.cloudLatencyMs / 1000).toFixed(1)}s</div>
      )}
    </div>
  );
}

// Concise, deterministic "why rejected" list — gate/result/detail strings
// from our own validators only. No model reasoning, no raw response.
function WhyRejectedView({ provenance }: { provenance: any }) {
  const failures: any[] = Array.isArray(provenance?.qualityFailures) ? provenance.qualityFailures : [];
  const missingRoles: any[] = Array.isArray(provenance?.missingRoles) ? provenance.missingRoles : [];
  if (failures.length === 0 && missingRoles.length === 0) return null;
  return (
    <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 8, textAlign: 'left' }}>
      <div className="panel-title" style={{ fontSize: 9, marginBottom: 4 }}>Why rejected</div>
      {failures.map((f: any, i: number) => (
        <div key={`qf-${i}`} style={{ color: 'var(--danger)' }}>• {String(f?.gate ?? '?')}: {String(f?.detail ?? '')}</div>
      ))}
      {missingRoles.length > 0 && (
        <div style={{ color: 'var(--danger)' }}>• Missing required roles: {missingRoles.map(String).join(', ')}</div>
      )}
    </div>
  );
}

export default function AgainPilotPanel({
  provider, platform, hasDesign,
  designId, designName, designStatus,
  onApply, onRefineApply, onClose,
}: Props) {
  // ── Mode ──
  const [mode, setMode] = useState<'generate' | 'refine'>('generate');

  // ── Generate state ──
  const [stage, setStage] = useState<Stage>('input');
  const [brief, setBrief] = useState('');
  const [providerPref, setProviderPref] = useState(provider || 'AWS');
  const [platformPref, setPlatformPref] = useState(platform || 'KUBERNETES');
  const [depth, setDepth] = useState('DETAILED');
  const [proposal, setProposal] = useState<any>(null);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const [resultMode, setResultMode] = useState('');
  const [provenance, setProvenance] = useState<any>(null);
  const [completeness, setCompleteness] = useState<any>(null);
  const [aiStatus, setAiStatus] = useState<{ mode: string; provider: string; model?: string; available: boolean } | null>(null);

  // ── Refine state ──
  const [refineInstruction, setRefineInstruction] = useState('');
  const [refineDelta, setRefineDelta] = useState<any>(null);
  const [refineProposal, setRefineProposal] = useState<any>(null);
  const [refineResultMode, setRefineResultMode] = useState('');
  const [refineCompleteness, setRefineCompleteness] = useState<any>(null);
  const [refineProvenance, setRefineProvenance] = useState<any>(null);
  const [refining, setRefining] = useState(false);

  useEffect(() => {
    api.againpilotStatus().then(s => setAiStatus(s)).catch(() => { });
  }, []);

  const statusLabel = aiStatus
    ? aiStatus.mode === 'REAL_LLM' ? `Local AI · ${aiStatus.model || 'LLM'} READY`
      : aiStatus.mode === 'AI_CONTROL_CENTER' ? `AI: Control Center`
        : `DETERMINISTIC FALLBACK`
    : 'AI: ...';

  const isFrozen = designStatus === 'BASELINE_FROZEN' || designStatus === 'FROZEN' || designStatus === 'ACCEPTED';

  // ── Generate ──
  const generate = async (forceMode?: string) => {
    if (!brief.trim()) return;
    setStage('generating'); setError(''); setResultMode(''); setProvenance(null);
    const stages = forceMode === 'DETERMINISTIC_FALLBACK'
      ? ['Generating deterministic architecture…', 'Validating architecture…']
      : ['Understanding architecture requirements…', 'Selecting relevant services…', 'Generating architecture…', 'Validating architecture…'];
    for (const s of stages) { setStatusMsg(s); await new Promise(r => setTimeout(r, 400)); }
    try {
      const result = await api.againpilotGenerate({
        brief: brief.trim(), providerPreference: providerPref, platformPreference: platformPref, generationDepth: depth, forceMode: forceMode || '',
      });
      if (result.needsFallbackConsent) { setResultMode(result.resultMode || 'FAILED'); setProvenance(result.provenance || null); setStage('fallback'); return; }
      setProposal(result.proposal); setResultMode(result.resultMode || result.generationMode || '');
      setProvenance(result.provenance || null); setCompleteness(result.completeness || null); setStage('review');
    } catch (e: any) { setError(e.message || 'Generation failed'); setStage('input'); }
  };

  const applyToCanvas = () => { if (proposal) { onApply(proposal); onClose(); } };

  // ── Refine ──
  const canRefine = hasDesign && designId && !isFrozen && !!provider;

  const runRefine = async (forceMode?: string) => {
    if (!refineInstruction.trim() || !canRefine || refining) return;
    setRefining(true); setStage('refining'); setError(''); setRefineResultMode('');
    const stages = ['Analyzing requested change…', 'Generating delta…', 'Validating architecture…'];
    for (const s of stages) { setStatusMsg(s); await new Promise(r => setTimeout(r, 400)); }
    try {
      const result = await api.againpilotRefine({
        designId, instruction: refineInstruction.trim(), provider,
        forceMode: forceMode || '',
        detectedRequirements: proposal?.detectedRequirements || {},
      });
      if (result.needsFallbackConsent) {
        setRefineResultMode(result.resultMode || 'FAILED'); setRefineProvenance(result.provenance || null); setStage('refine-fallback'); setRefining(false); return;
      }
      setRefineProposal(result.proposal);
      setRefineDelta(result.delta || null);
      setRefineCompleteness(result.completeness || null);
      setRefineResultMode(result.resultMode || '');
      setRefineProvenance(result.provenance || null);
      setStage('refine-preview');
    } catch (e: any) { setError(e.message || 'Refinement failed'); setStage('refine-failed'); }
    setRefining(false);
  };

  const applyRefine = async () => {
    if (!refineProposal || !designId || !onRefineApply) return;
    setStage('refine-applying');
    try {
      await onRefineApply(designId, refineProposal);
      setStage('refine-applied');
      // Auto-close after brief display
      setTimeout(() => onClose(), 1500);
    } catch (e: any) { setError(e.message || 'Apply failed'); setStage('refine-failed'); }
  };

  const cancelRefine = () => {
    setRefineProposal(null); setRefineDelta(null); setRefineInstruction('');
    setStage('input');
  };

  const closePanel = () => { onClose(); };

  const selectExample = (b: string) => { setBrief(b); };

  // ── Render helpers ──
  const delta = refineDelta;
  const changedNodes = delta?.changedNodes || [];
  const addedNodes = delta?.addedNodes || [];
  const removedNodes = delta?.removedNodes || [];
  const addedEdges = delta?.addedEdges || [];
  const removedEdges = delta?.removedEdges || [];
  const changedEdges: any[] = []; // delta format doesn't have changedEdges yet

  return (
    <div className="modal-overlay" onClick={closePanel}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 640, maxHeight: '90vh', overflow: 'auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <div className="panel-title" style={{ fontSize: 14 }}>AGAINPILOT</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Describe what you want to build</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={closePanel}>×</button>
        </div>

        {/* AI Status */}
        <div style={{ marginBottom: 10 }}>
          <span className={`badge ${aiStatus?.mode === 'REAL_LLM' ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: 9 }}>{statusLabel}</span>
        </div>

        {/* Mode Tabs (if hasDesign) */}
        {hasDesign && (
          <div style={{ display: 'flex', gap: 0, marginBottom: 12, borderBottom: '1px solid var(--border)' }}>
            <button onClick={() => { setMode('generate'); setStage('input'); }}
              className={mode === 'generate' ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm'}
              style={{ borderRadius: '4px 4px 0 0', borderBottom: mode === 'generate' ? '2px solid var(--accent)' : 'none' }}>
              Generate
            </button>
            <button onClick={() => { setMode('refine'); setStage('refine-input'); }}
              className={mode === 'refine' ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm'}
              disabled={!canRefine}
              style={{ borderRadius: '4px 4px 0 0', borderBottom: mode === 'refine' ? '2px solid var(--accent)' : 'none' }}>
              Refine
            </button>
          </div>
        )}

        {/* ── Design context for refine ── */}
        {mode === 'refine' && designId && (
          <div style={{ marginBottom: 8, padding: 8, background: 'var(--bg-elevated)', borderRadius: 4, fontSize: 9 }}>
            <div style={{ color: 'var(--text-muted)' }}>Selected Design:</div>
            <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{designName || designId}</div>
            <div style={{ color: 'var(--text-muted)' }}>{designId} · <span className={`badge ${isFrozen ? 'badge-danger' : 'badge-info'}`}>{designStatus || 'DRAFT'}</span></div>
          </div>
        )}

        {/* ── Frozen design warning ── */}
        {mode === 'refine' && isFrozen && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)', fontSize: 11 }}>
            <div style={{ color: 'var(--danger)', fontWeight: 500, marginBottom: 8 }}>This design is frozen. Create a new revision to make changes.</div>
            <button className="btn btn-ghost btn-sm" onClick={closePanel}>Close</button>
          </div>
        )}

        {/* ── No design selected ── */}
        {mode === 'refine' && !designId && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)', fontSize: 11 }}>
            Select a design before refining architecture.
          </div>
        )}

        {/* ── Provider unresolved — refuse to refine against an unknown/
            possibly-wrong provider rather than silently defaulting ── */}
        {mode === 'refine' && designId && !isFrozen && !provider && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)', fontSize: 11 }}>
            <div style={{ color: 'var(--danger)', fontWeight: 500, marginBottom: 8 }}>DESIGN_PROVIDER_UNRESOLVED</div>
            <div>This design's architecture could not be hydrated, so its cloud provider is unknown. Refining would validate against the wrong provider. Reload the design or check its persisted data before refining.</div>
          </div>
        )}

        {/* ═══════════ GENERATING ═══════════ */}
        {stage === 'generating' && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div className="loading" style={{ marginBottom: 16 }}>{statusMsg}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Generating architecture proposal…</div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 8 }}>
              {aiStatus?.mode === 'REAL_LLM' ? `Using: ${aiStatus.provider} · ${aiStatus.model}` : 'Deterministic mode'}
            </div>
          </div>
        )}

        {/* ═══════════ FALLBACK ═══════════ */}
        {stage === 'fallback' && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <div style={{ fontSize: 13, color: 'var(--warning)', fontWeight: 500, marginBottom: 12 }}>Real AI generation failed or timed out.</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
              Reason: <span className="mono">{resultMode || 'UNKNOWN'}</span>
            </div>
            <ExecutionPathView provenance={provenance} />
            <WhyRejectedView provenance={provenance} />
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 16 }}>No deterministic architecture has been generated yet. Choose how to proceed.</div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn btn-primary btn-sm" onClick={() => generate()}>Retry Real AI</button>
              <button className="btn btn-secondary btn-sm" onClick={() => generate('DETERMINISTIC_FALLBACK')}>Use Deterministic Fallback</button>
              <button className="btn btn-ghost btn-sm" onClick={closePanel}>Cancel</button>
            </div>
          </div>
        )}

        {/* ═══════════ REFINE FALLBACK ═══════════ */}
        {stage === 'refine-fallback' && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <div style={{ fontSize: 13, color: 'var(--warning)', fontWeight: 500, marginBottom: 12 }}>Real AI refinement failed or timed out.</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>Reason: <span className="mono">{refineResultMode || 'UNKNOWN'}</span></div>
            <ExecutionPathView provenance={refineProvenance} />
            <WhyRejectedView provenance={refineProvenance} />
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 16 }}>The current architecture is unchanged.</div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn btn-primary btn-sm" onClick={() => runRefine()}>Retry Real AI</button>
              <button className="btn btn-secondary btn-sm" onClick={() => runRefine('DETERMINISTIC_FALLBACK')}>Use Deterministic Fallback</button>
              <button className="btn btn-ghost btn-sm" onClick={cancelRefine}>Cancel</button>
            </div>
          </div>
        )}

        {/* ═══════════ REFINING ═══════════ */}
        {stage === 'refining' && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div className="loading" style={{ marginBottom: 16 }}>{statusMsg}</div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 8 }}>
              {aiStatus?.mode === 'REAL_LLM' ? `Using: ${aiStatus.provider} · ${aiStatus.model}` : 'Deterministic mode'}
            </div>
          </div>
        )}

        {/* ═══════════ REFINE INPUT ═══════════ */}
        {mode === 'refine' && stage === 'refine-input' && canRefine && (
          <div>
            <div className="panel-title" style={{ fontSize: 10, marginBottom: 6 }}>Describe the architecture change you want…</div>
            {/* Example chips */}
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
              {REFINE_EXAMPLES.map((ex, i) => (
                <button key={i} onClick={() => setRefineInstruction(ex)}
                  className="btn btn-ghost btn-sm" style={{ fontSize: 8 }}>
                  {ex}
                </button>
              ))}
            </div>
            <textarea className="form-input"
              placeholder="Describe the architecture change you want..."
              value={refineInstruction}
              onChange={e => setRefineInstruction(e.target.value)}
              style={{ minHeight: 80, resize: 'vertical', fontSize: 12, lineHeight: 1.5 }} />
            {error && (
              <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--danger)', borderRadius: 4, fontSize: 10, color: 'var(--danger)' }}>{error}</div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn btn-primary" onClick={() => runRefine()} disabled={!refineInstruction.trim() || refining} style={{ flex: 1 }}>
                Refine Architecture
              </button>
              <button className="btn btn-ghost" onClick={closePanel}>Cancel</button>
            </div>
          </div>
        )}

        {/* ═══════════ REFINE PREVIEW ═══════════ */}
        {stage === 'refine-preview' && refineProposal && (
          <div>
            <div className="badge badge-success mb-sm" style={{ fontSize: 10 }}>
              Refinement preview{refineProvenance?.requestPolicy ? '' : ` — ${refineResultMode === 'REAL_LLM' || refineResultMode === 'REAL_LLM_WITH_LLM_CORRECTION' ? `Local AI · ${aiStatus?.model || 'LLM'}` : refineResultMode}`}
            </div>
            <ExecutionPathView provenance={refineProvenance} />
            {refineProvenance && !refineProvenance.requestPolicy && (
              <div style={{ fontSize: 8, color: 'var(--text-muted)', marginBottom: 4 }}>
                Latency: {((refineProvenance.stage1Ms ?? 0) / 1000).toFixed(1)}s
                {refineResultMode === 'REAL_LLM_WITH_LLM_CORRECTION' && ` (auto-corrected in ${((refineProvenance.correctionMs ?? 0) / 1000).toFixed(1)}s)`}
              </div>
            )}

            {/* Quality + Completeness */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <span className={`badge ${refineCompleteness?.overall === 'FAIL' ? 'badge-danger' : refineCompleteness?.overall === 'WARN' ? 'badge-warning' : 'badge-success'}`} style={{ fontSize: 9 }}>
                QUALITY={refineCompleteness?.overall === 'FAIL' ? 'FAIL' : 'PASS'}
              </span>
              <span className={`badge ${(refineCompleteness?.missingRoles || []).length > 0 ? 'badge-danger' : 'badge-success'}`} style={{ fontSize: 9 }}>
                COMPLETENESS={(refineCompleteness?.missingRoles || []).length === 0 ? 'PASS' : 'FAIL'}
              </span>
            </div>

            {/* Change Preview */}
            <div style={{ marginBottom: 8 }}>
              <div className="panel-title" style={{ fontSize: 10, marginBottom: 6 }}>Change Preview</div>

              {/* Changed Nodes */}
              {changedNodes.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--accent)', marginBottom: 4 }}>Changed Components ({changedNodes.length})</div>
                  <table style={{ width: '100%', fontSize: 9, borderCollapse: 'collapse' }}>
                    <thead><tr style={{ color: 'var(--text-muted)' }}><th style={{ textAlign: 'left', padding: 2 }}>Component</th><th style={{ textAlign: 'left', padding: 2 }}>Property</th><th style={{ textAlign: 'left', padding: 2 }}>Before</th><th style={{ textAlign: 'left', padding: 2 }}>After</th></tr></thead>
                    <tbody>
                      {changedNodes.map((cn: any, i: number) => (
                        <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                          <td style={{ padding: '4px 2px', color: 'var(--text-primary)' }}>{cn.nodeId}</td>
                          <td style={{ padding: '4px 2px' }}>{cn.field}</td>
                          <td style={{ padding: '4px 2px', color: 'var(--danger)' }}>{cn.oldValue}</td>
                          <td style={{ padding: '4px 2px', color: 'var(--success)' }}>{cn.newValue}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Added Nodes */}
              {addedNodes.length > 0 && (
                <div style={{ marginBottom: 4 }}>
                  <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--success)', marginBottom: 2 }}>Added Components ({addedNodes.length})</div>
                  {addedNodes.map((an: any, i: number) => (
                    <div key={i} style={{ fontSize: 9, color: 'var(--text-secondary)', paddingLeft: 8 }}>
                      + {an.nodeId || an.name || 'Unknown'} {an.nativeService ? `(${an.nativeService})` : ''}
                    </div>
                  ))}
                </div>
              )}

              {/* Removed Nodes */}
              {removedNodes.length > 0 && (
                <div style={{ marginBottom: 4 }}>
                  <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--danger)', marginBottom: 2 }}>Removed Components ({removedNodes.length})</div>
                  {removedNodes.map((rn: any, i: number) => (
                    <div key={i} style={{ fontSize: 9, color: 'var(--text-secondary)', paddingLeft: 8 }}>
                      − {typeof rn === 'string' ? rn : rn.nodeId || rn}
                    </div>
                  ))}
                </div>
              )}

              {/* Added Edges */}
              {addedEdges.length > 0 && (
                <div style={{ marginBottom: 4 }}>
                  <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--success)', marginBottom: 2 }}>Added Connections ({addedEdges.length})</div>
                  {addedEdges.map((ae: any, i: number) => (
                    <div key={i} style={{ fontSize: 9, color: 'var(--text-secondary)', paddingLeft: 8 }}>
                      + {ae.sourceNodeId || ae.from} → {ae.targetNodeId || ae.to} {ae.label ? `(${ae.label})` : ''}
                    </div>
                  ))}
                </div>
              )}

              {/* Removed Edges */}
              {removedEdges.length > 0 && (
                <div style={{ marginBottom: 4 }}>
                  <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--danger)', marginBottom: 2 }}>Removed Connections ({removedEdges.length})</div>
                  {removedEdges.map((re: any, i: number) => (
                    <div key={i} style={{ fontSize: 9, color: 'var(--text-secondary)', paddingLeft: 8 }}>
                      − {typeof re === 'string' ? re : re.edgeId || re}
                    </div>
                  ))}
                </div>
              )}

              {(changedNodes.length === 0 && addedNodes.length === 0 && removedNodes.length === 0 && addedEdges.length === 0 && removedEdges.length === 0) && (
                <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>No structural changes detected.</div>
              )}
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={applyRefine} disabled={refining}
                style={{ flex: 1 }}>
                {refining ? 'Applying…' : 'Apply Changes'}
              </button>
              <button className="btn btn-ghost" onClick={cancelRefine}>Cancel</button>
            </div>
          </div>
        )}

        {/* ═══════════ REFINE APPLIED ═══════════ */}
        {stage === 'refine-applied' && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <div className="badge badge-success" style={{ fontSize: 12, marginBottom: 8 }}>Changes Applied</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Architecture updated successfully.</div>
          </div>
        )}

        {/* ═══════════ REFINE FAILED ═══════════ */}
        {stage === 'refine-failed' && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <div style={{ fontSize: 13, color: 'var(--danger)', fontWeight: 500, marginBottom: 12 }}>Apply Failed</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 12 }}>{error || 'Unknown error'}</div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn btn-primary btn-sm" onClick={applyRefine}>Retry</button>
              <button className="btn btn-ghost btn-sm" onClick={cancelRefine}>Cancel</button>
            </div>
          </div>
        )}

        {/* ═══════════ GENERATE INPUT ═══════════ */}
        {mode === 'generate' && stage === 'input' && (
          <>
            <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
              {EXAMPLES.map((ex, i) => (
                <button key={i} onClick={() => selectExample(ex.brief)} className="btn btn-ghost btn-sm" style={{ fontSize: 9, textAlign: 'left', maxWidth: 200 }}>
                  <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{ex.title}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 8, whiteSpace: 'normal' }}>{ex.brief.slice(0, 80)}…</div>
                </button>
              ))}
            </div>
            <textarea className="form-input"
              placeholder="Build a patient portal on AWS for 10,000 users/day. The database must be private. Applications should be containerized…"
              value={brief} onChange={e => setBrief(e.target.value)}
              style={{ minHeight: 120, resize: 'vertical', fontSize: 12, lineHeight: 1.5 }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <select className="form-select" value={providerPref} onChange={e => setProviderPref(e.target.value)} style={{ fontSize: 10, flex: 1 }}>
                <option value="AUTO">Auto Detect Provider</option>
                <option value="AWS">AWS</option><option value="GCP">GCP</option><option value="ON_PREM">On-Prem</option><option value="PRIVATE_CLOUD">Private Cloud</option>
              </select>
              <select className="form-select" value={platformPref} onChange={e => setPlatformPref(e.target.value)} style={{ fontSize: 10, flex: 1 }}>
                <option value="AUTO">Auto Platform</option>
                <option value="KUBERNETES">Kubernetes</option><option value="NATIVE_VM">Virtual Machines</option><option value="OPENSHIFT_OCP">OpenShift</option><option value="BARE_METAL">Bare Metal</option>
              </select>
              <select className="form-select" value={depth} onChange={e => setDepth(e.target.value)} style={{ fontSize: 10, flex: 1 }}>
                <option value="HIGH_LEVEL">High Level</option><option value="DETAILED">Detailed</option>
              </select>
            </div>
            {error && (
              <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--danger)', borderRadius: 4, fontSize: 10, color: 'var(--danger)' }}>
                {error}
              </div>
            )}
            <button className="btn btn-primary" onClick={() => generate()} disabled={!brief.trim()} style={{ width: '100%', marginTop: 12 }}>
              Generate Architecture
            </button>
          </>
        )}

        {/* ═══════════ GENERATE REVIEW ═══════════ */}
        {mode === 'generate' && stage === 'review' && proposal && (
          <div>
            <div className="badge badge-success mb-sm" style={{ fontSize: 10 }}>
              Architecture generated{provenance?.requestPolicy ? '' : resultMode.includes('REAL_LLM') ? ` by Local AI · ${aiStatus?.model || 'LLM'}` : resultMode === 'DETERMINISTIC_FALLBACK' ? ' by Deterministic Fallback' : ''}
            </div>
            <ExecutionPathView provenance={provenance} />
            {provenance && !provenance.requestPolicy && (
              <div style={{ fontSize: 8, color: 'var(--text-muted)', marginBottom: 4 }}>
                S1: {((provenance.stage1LatencyMs ?? provenance.stage1Ms ?? 0) / 1000).toFixed(1)}s · S2: {((provenance.stage2LatencyMs ?? provenance.stage2Ms ?? 0) / 1000).toFixed(1)}s
                {resultMode === 'REAL_LLM_WITH_LLM_CORRECTION' && ` (corrected in ${((provenance.correctionLatencyMs ?? 0) / 1000).toFixed(1)}s)`}
              </div>
            )}
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>{proposal.title}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 12 }}>{proposal.summary}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, marginBottom: 12, fontSize: 10 }}>
              <div>Nodes: {proposal.nodes?.length || 0}</div>
              <div>Edges: {proposal.edges?.length || 0}</div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={applyToCanvas} style={{ flex: 1 }}>
                {hasDesign ? 'Apply to Canvas' : 'Create Design & Apply'}
              </button>
              <button className="btn btn-ghost" onClick={closePanel}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
