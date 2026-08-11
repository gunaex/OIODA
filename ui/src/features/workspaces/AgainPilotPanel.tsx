/* AGAINPILOT — AI Architecture Copilot Panel.
   Natural language → Canonical Architecture → draw.io. */
import { useState, useEffect, useCallback } from 'react';
import { api } from '../../lib/api';

interface Props {
  provider: string;
  platform: string;
  hasDesign: boolean;
  onApply: (proposal: any) => void;
  onClose: () => void;
}

const EXAMPLES = [
  {
    title: 'Patient Portal',
    brief: `Build a patient portal on AWS for 10,000 users/day.
Use private database access, containerized workloads,
high availability and PDPA-aligned security.`,
  },
  {
    title: 'Enterprise Internal App',
    brief: `Build an internal enterprise web application on-premise
using Kubernetes, PostgreSQL, private networking,
SSO and highly available application services.`,
  },
  {
    title: 'Data Platform',
    brief: `Design a cloud data platform that receives batch and streaming data,
stores raw and curated datasets, provides analytics,
and separates public ingress from private data services.`,
  },
];

type Stage = 'input' | 'generating' | 'review' | 'fallback' | 'refine-input' | 'refining' | 'refine-fallback';

export default function AgainPilotPanel({ provider, platform, hasDesign, onApply, onClose }: Props) {
  const [stage, setStage] = useState<Stage>('input');
  const [brief, setBrief] = useState('');
  const [providerPref, setProviderPref] = useState(provider || 'AWS');
  const [platformPref, setPlatformPref] = useState(platform || 'KUBERNETES');
  const [depth, setDepth] = useState('DETAILED');
  const [proposal, setProposal] = useState<any>(null);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const [resultMode, setResultMode] = useState('');  // REAL_LLM / DETERMINISTIC_FALLBACK / FAILED
  const [provenance, setProvenance] = useState<any>(null);
  const [completeness, setCompleteness] = useState<any>(null);
  const [aiStatus, setAiStatus] = useState<{ mode: string; provider: string; model?: string; available: boolean } | null>(null);
  const [refineInstruction, setRefineInstruction] = useState('');
  const [refineDelta, setRefineDelta] = useState<any>(null);
  const [refineResultMode, setRefineResultMode] = useState('');

  useEffect(() => {
    api.againpilotStatus().then(s => setAiStatus(s)).catch(() => { });
  }, []);

  const statusLabel = aiStatus
    ? aiStatus.mode === 'REAL_LLM'
      ? `Local AI · ${aiStatus.model || 'LLM'} READY`
      : aiStatus.mode === 'AI_CONTROL_CENTER' ? `AI: Control Center`
        : `DETERMINISTIC FALLBACK`
    : 'AI: ...';

  // forceMode: pass 'DETERMINISTIC_FALLBACK' only when the user has explicitly
  // chosen it (the "Use Deterministic Fallback" button below). Any other call
  // tries real AI; if real AI genuinely fails, the backend returns
  // needsFallbackConsent instead of silently generating a deterministic
  // result — that consent decision belongs to the user, not this function.
  const generate = async (forceMode?: string) => {
    if (!brief.trim()) return;
    setStage('generating');
    setError('');
    setResultMode('');
    setProvenance(null);

    const stages = forceMode === 'DETERMINISTIC_FALLBACK'
      ? ['Generating deterministic architecture…', 'Validating architecture…']
      : ['Understanding architecture requirements…', 'Selecting relevant services…', 'Generating architecture…', 'Validating architecture…'];
    for (const s of stages) { setStatusMsg(s); await new Promise(r => setTimeout(r, 400)); }

    try {
      const result = await api.againpilotGenerate({
        brief: brief.trim(),
        providerPreference: providerPref,
        platformPreference: platformPref,
        generationDepth: depth,
        forceMode: forceMode || '',
      });
      if (result.needsFallbackConsent) {
        // Real AI failed. Nothing was generated — no deterministic proposal
        // is silently sitting behind this screen. The user picks what
        // happens next.
        setResultMode(result.resultMode || 'FAILED');
        setProvenance(result.provenance || null);
        setStage('fallback');
        return;
      }
      const rm = result.resultMode || result.generationMode || '';
      setProposal(result.proposal);
      setResultMode(rm);
      setProvenance(result.provenance || null);
      setCompleteness(result.completeness || null);
      setStage('review');
    } catch (e: any) {
      setError(e.message || 'Generation failed');
      setStage('input');
    }
  };

  const retryRealAI = () => generate();
  const useFallback = () => generate('DETERMINISTIC_FALLBACK');

  const applyToCanvas = () => {
    if (proposal) { onApply(proposal); onClose(); }
  };

  const selectExample = (exampleBrief: string) => {
    setBrief(exampleBrief);
  };

  const openRefine = () => {
    setRefineInstruction('');
    setStage('refine-input');
  };

  const runRefine = async (forceMode?: string) => {
    if (!refineInstruction.trim() || !proposal) return;
    setStage('refining');
    setError('');
    try {
      const result = await api.againpilotRefine({
        instruction: refineInstruction.trim(),
        nodes: proposal.nodes || [],
        edges: proposal.edges || [],
        provider: proposal.detectedRequirements?.provider || providerPref,
        forceMode: forceMode || '',
        // Carries the original brief's HA/compliance/security signals so the
        // post-refine validation doesn't lose them (see
        // _merge_refine_requirements on the backend).
        detectedRequirements: proposal.detectedRequirements || {},
      });
      if (result.needsFallbackConsent) {
        setRefineResultMode(result.resultMode || 'FAILED');
        setProvenance(result.provenance || null);
        setStage('refine-fallback');
        return;
      }
      // Refine returns the FULL updated canonical model, not just UI text —
      // replace the proposal outright so the delta preview and the eventual
      // Apply both operate on the real updated architecture.
      setProposal(result.proposal);
      setRefineDelta(result.delta || null);
      setCompleteness(result.completeness || null);
      setResultMode(result.resultMode || '');
      setProvenance(result.provenance || null);
      setStage('review');
    } catch (e: any) {
      setError(e.message || 'Refinement failed');
      setStage('refine-input');
    }
  };

  const retryRefineRealAI = () => runRefine();
  const useRefineFallback = () => runRefine('DETERMINISTIC_FALLBACK');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 640, maxHeight: '90vh', overflow: 'auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <div className="panel-title" style={{ fontSize: 14 }}>AGAINPILOT</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Describe what you want to build</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>×</button>
        </div>

        {/* AI Status */}
        <div style={{ marginBottom: 10 }}>
          <span className={`badge ${aiStatus?.mode === 'REAL_LLM' ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: 9 }}>
            {statusLabel}
          </span>
        </div>

        {stage === 'generating' && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div className="loading" style={{ marginBottom: 16 }}>{statusMsg}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Generating architecture proposal…</div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 8 }}>
              {aiStatus?.mode === 'REAL_LLM' ? `Using: ${aiStatus.provider} · ${aiStatus.model}` : 'Deterministic mode'}
            </div>
          </div>
        )}

        {stage === 'fallback' && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <div style={{ fontSize: 13, color: 'var(--warning)', fontWeight: 500, marginBottom: 12 }}>
              Real AI generation failed or timed out.
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
              Reason: <span className="mono">{resultMode || 'UNKNOWN'}</span>
              {provenance?.completenessResult === 'FAIL' && ' — the proposal was missing required architecture roles'}
              {provenance?.qualityResult === 'FAIL' && provenance?.completenessResult !== 'FAIL' && ' — the proposal failed architecture quality checks'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 16 }}>
              No deterministic architecture has been generated yet. Choose how to proceed.
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn btn-primary btn-sm" onClick={retryRealAI}>Retry Real AI</button>
              <button className="btn btn-secondary btn-sm" onClick={useFallback}>Use Deterministic Fallback</button>
              <button className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
            </div>
          </div>
        )}

        {stage === 'refine-fallback' && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <div style={{ fontSize: 13, color: 'var(--warning)', fontWeight: 500, marginBottom: 12 }}>
              Real AI refinement failed or timed out.
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
              Reason: <span className="mono">{refineResultMode || 'UNKNOWN'}</span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 16 }}>
              The current architecture is unchanged. Choose how to proceed with your refinement instruction.
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn btn-primary btn-sm" onClick={retryRefineRealAI}>Retry Real AI</button>
              <button className="btn btn-secondary btn-sm" onClick={useRefineFallback}>Use Deterministic Fallback</button>
              <button className="btn btn-ghost btn-sm" onClick={() => setStage('review')}>Cancel</button>
            </div>
          </div>
        )}

        {stage === 'refining' && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div className="loading" style={{ marginBottom: 16 }}>Applying refinement…</div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 8 }}>
              {aiStatus?.mode === 'REAL_LLM' ? `Using: ${aiStatus.provider} · ${aiStatus.model}` : 'Deterministic mode'}
            </div>
          </div>
        )}

        {stage === 'refine-input' && (
          <div>
            <div className="panel-title" style={{ fontSize: 10, marginBottom: 6 }}>Refine Architecture</div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 8 }}>
              Describe the change. This updates the actual architecture (nodes/edges), not just this panel's text.
            </div>
            <textarea
              className="form-input"
              placeholder="Use ECS Fargate for the application tier and ensure the database has no public route…"
              value={refineInstruction}
              onChange={e => setRefineInstruction(e.target.value)}
              style={{ minHeight: 80, resize: 'vertical', fontSize: 12, lineHeight: 1.5 }}
            />
            {error && (
              <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--danger)', borderRadius: 4, fontSize: 10, color: 'var(--danger)' }}>
                {error}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn btn-primary" onClick={() => runRefine()} disabled={!refineInstruction.trim()} style={{ flex: 1 }}>
                Preview Refinement
              </button>
              <button className="btn btn-ghost" onClick={() => setStage('review')}>Cancel</button>
            </div>
          </div>
        )}

        {stage === 'input' && (
          <>
            {/* Example prompts */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
              {EXAMPLES.map((ex, i) => (
                <button key={i} onClick={() => selectExample(ex.brief)}
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: 9, textAlign: 'left', maxWidth: 200 }}>
                  <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{ex.title}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 8, whiteSpace: 'normal' }}>{ex.brief.slice(0, 80)}…</div>
                </button>
              ))}
            </div>

            {/* Brief textarea */}
            <textarea
              className="form-input"
              placeholder="Build a patient portal on AWS for 10,000 users/day. The database must be private. Applications should be containerized…"
              value={brief}
              onChange={e => setBrief(e.target.value)}
              style={{ minHeight: 120, resize: 'vertical', fontSize: 12, lineHeight: 1.5 }}
            />

            {/* Options row */}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <select className="form-select" value={providerPref} onChange={e => setProviderPref(e.target.value)} style={{ fontSize: 10, flex: 1 }}>
                <option value="AUTO">Auto Detect Provider</option>
                <option value="AWS">AWS</option>
                <option value="GCP">GCP</option>
                <option value="ON_PREM">On-Prem</option>
                <option value="PRIVATE_CLOUD">Private Cloud</option>
              </select>
              <select className="form-select" value={platformPref} onChange={e => setPlatformPref(e.target.value)} style={{ fontSize: 10, flex: 1 }}>
                <option value="AUTO">Auto Platform</option>
                <option value="KUBERNETES">Kubernetes</option>
                <option value="NATIVE_VM">Virtual Machines</option>
                <option value="OPENSHIFT_OCP">OpenShift</option>
                <option value="BARE_METAL">Bare Metal</option>
              </select>
              <select className="form-select" value={depth} onChange={e => setDepth(e.target.value)} style={{ fontSize: 10, flex: 1 }}>
                <option value="HIGH_LEVEL">High Level</option>
                <option value="DETAILED">Detailed</option>
              </select>
            </div>

            {error && (
              <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--danger)', borderRadius: 4, fontSize: 10, color: 'var(--danger)' }}>
                {error}
                <div style={{ marginTop: 4, display: 'flex', gap: 4 }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => generate()}>Retry</button>
                  <button className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
                </div>
              </div>
            )}

            <button
              className="btn btn-primary"
              onClick={() => generate()}
              disabled={!brief.trim()}
              style={{ width: '100%', marginTop: 12 }}>
              Generate Architecture
            </button>
          </>
        )}

        {/* Review Stage */}
        {stage === 'review' && proposal && (
          <div>
            <div className="badge badge-success mb-sm" style={{ fontSize: 10 }}>
              Architecture generated
              {resultMode === 'REAL_LLM' || resultMode === 'REAL_LLM_WITH_LLM_CORRECTION'
                ? ` by Local AI · ${aiStatus?.model || 'LLM'}`
                : resultMode === 'DETERMINISTIC_FALLBACK'
                  ? ' by Deterministic Fallback'
                  : ''}
            </div>
            {provenance && (
              <div style={{ fontSize: 8, color: 'var(--text-muted)', marginBottom: 4 }}>
                Stage 1: {((provenance.stage1LatencyMs ?? provenance.stage1Ms ?? 0) / 1000).toFixed(1)}s ·
                {' '}Stage 2: {((provenance.stage2LatencyMs ?? provenance.stage2Ms ?? 0) / 1000).toFixed(1)}s
                {resultMode === 'REAL_LLM_WITH_LLM_CORRECTION' && ` (auto-corrected in ${((provenance.correctionLatencyMs ?? 0) / 1000).toFixed(1)}s)`}
              </div>
            )}
            {completeness && (
              <div style={{ fontSize: 9, marginBottom: 8, color: completeness.overall === 'FAIL' ? 'var(--danger)' : completeness.overall === 'WARN' ? 'var(--warning)' : 'var(--text-muted)' }}>
                Completeness: {completeness.overall}
                {(completeness.missingRoles || []).length > 0 && ` — missing: ${completeness.missingRoles.join(', ')}`}
              </div>
            )}
            {refineDelta && (
              <div style={{ marginBottom: 8, padding: 8, background: 'var(--bg-elevated)', borderRadius: 4 }}>
                <div className="panel-title" style={{ fontSize: 9, marginBottom: 4 }}>Last Refinement Applied</div>
                <div style={{ fontSize: 9, color: 'var(--text-secondary)' }}>{refineDelta.summary}</div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>
                  +{(refineDelta.addedNodes || []).length} nodes · -{(refineDelta.removedNodes || []).length} nodes ·
                  {' '}~{(refineDelta.changedNodes || []).length} changed ·
                  {' '}+{(refineDelta.addedEdges || []).length} edges · -{(refineDelta.removedEdges || []).length} edges
                </div>
              </div>
            )}

            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
              {proposal.title}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 12 }}>
              {proposal.summary}
            </div>

            {/* Detected Requirements */}
            <div style={{ marginBottom: 8 }}>
              <div className="panel-title" style={{ fontSize: 10, marginBottom: 4 }}>Detected Requirements</div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', fontSize: 9 }}>
                <span className="badge badge-info">{proposal.detectedRequirements?.provider || '?'}</span>
                <span className="badge badge-neutral">{proposal.detectedRequirements?.expectedLoad || '?'}</span>
                {(proposal.detectedRequirements?.availability || []).map((a: string, i: number) => (
                  <span key={i} className="badge badge-success">{a}</span>
                ))}
                {(proposal.detectedRequirements?.compliance || []).map((c: string, i: number) => (
                  <span key={i} className="badge badge-warning">{c}</span>
                ))}
              </div>
            </div>

            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, marginBottom: 12, fontSize: 10 }}>
              <div><span className="text-muted">Nodes:</span> <span style={{ color: 'var(--text-primary)' }}>{proposal.nodes?.length || 0}</span></div>
              <div><span className="text-muted">Edges:</span> <span style={{ color: 'var(--text-primary)' }}>{proposal.edges?.length || 0}</span></div>
              <div><span className="text-muted">Arch View:</span> {proposal.views?.architecture?.nodes?.length || 0} nodes</div>
              <div><span className="text-muted">Data View:</span> {proposal.views?.dataFlow?.nodes?.length || 0} nodes</div>
              <div><span className="text-muted">Ops View:</span> {proposal.views?.operationFlow?.nodes?.length || 0} nodes</div>
              <div><span className="text-muted">Sec View:</span> {proposal.views?.securityFlow?.nodes?.length || 0} nodes</div>
            </div>

            {/* Service Recommendations */}
            {(proposal.nativeServiceRecommendations || []).length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div className="panel-title" style={{ fontSize: 10, marginBottom: 4 }}>Recommended Native Services</div>
                {proposal.nativeServiceRecommendations.slice(0, 8).map((r: any, i: number) => (
                  <div key={i} style={{ fontSize: 9, color: 'var(--text-secondary)', padding: '2px 0' }}>
                    <span className="mono" style={{ color: 'var(--accent)' }}>{r.service}</span>
                    <span className="text-muted"> — {r.description || r.rationale?.slice(0, 60)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Assumptions */}
            {(proposal.assumptions || []).length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div className="panel-title" style={{ fontSize: 10, marginBottom: 4 }}>Assumptions</div>
                {proposal.assumptions.map((a: string, i: number) => (
                  <div key={i} style={{ fontSize: 9, color: 'var(--text-muted)' }}>• {a}</div>
                ))}
              </div>
            )}

            {/* Risks */}
            {(proposal.risks || []).length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div className="panel-title" style={{ fontSize: 10, marginBottom: 4, color: 'var(--warning)' }}>Risks</div>
                {proposal.risks.map((r: string, i: number) => (
                  <div key={i} style={{ fontSize: 9, color: 'var(--warning)' }}>⚠ {r}</div>
                ))}
              </div>
            )}

            {/* Questions */}
            {(proposal.clarifyingQuestions || []).length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div className="panel-title" style={{ fontSize: 10, marginBottom: 4 }}>Clarifying Questions</div>
                {proposal.clarifyingQuestions.map((q: string, i: number) => (
                  <div key={i} style={{ fontSize: 9, color: 'var(--text-secondary)' }}>? {q}</div>
                ))}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={applyToCanvas} style={{ flex: 1 }}>
                {hasDesign ? 'Apply to Canvas' : 'Create Design & Apply'}
              </button>
              <button className="btn btn-secondary" onClick={openRefine}>
                Refine
              </button>
              <button className="btn btn-ghost" onClick={onClose}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
