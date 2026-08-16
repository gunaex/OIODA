import React, { useState, useEffect } from 'react';
import {
  SandboxTarget, SandboxApproval, SandboxExecution,
  SandboxPreflightResult, ExecutionFidelity,
  FIDELITY_COLORS, FIDELITY_LABELS, FIDELITY_WARNINGS,
  STATE_COLORS,
} from './sandboxTypes';

const API = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_API_URL) || '';

async function api<T = any>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + url, init);
  if (!r.ok) {
    const body = await r.text().catch(() => '');
    throw new Error(`HTTP ${r.status}: ${body.slice(0, 200)}`);
  }
  return r.json();
}

// ── Fidelity Badge ──────────────────────────────────────
function FidelityBadge({ fid }: { fid: ExecutionFidelity }) {
  const color = FIDELITY_COLORS[fid] || '#6b7280';
  const label = FIDELITY_LABELS[fid] || fid;
  const warning = FIDELITY_WARNINGS[fid] || '';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        background: color, color: '#fff', padding: '2px 10px',
        borderRadius: 4, fontSize: 13, fontWeight: 700,
      }}>
        {label}
      </span>
      {warning && <span style={{ fontSize: 11, color: color, fontWeight: 600 }}>{warning}</span>}
    </span>
  );
}

// ── State Badge ─────────────────────────────────────────
function StateBadge({ state }: { state: string }) {
  const color = STATE_COLORS[state] || '#6b7280';
  return (
    <span style={{
      background: color, color: '#fff', padding: '1px 8px',
      borderRadius: 3, fontSize: 12, fontWeight: 600,
    }}>
      {state.replace(/_/g, ' ')}
    </span>
  );
}

// ── Section ─────────────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20, padding: 14, background: '#1f2937', borderRadius: 8, border: '1px solid #374151' }}>
      <h3 style={{ margin: '0 0 10px', color: '#f3f4f6', fontSize: 15 }}>{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 13 }}>
      <span style={{ color: '#9ca3af' }}>{label}</span>
      <span style={{ color: color || '#e5e7eb', fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════
export default function SandboxExecutionPage() {
  const [targets, setTargets] = useState<SandboxTarget[]>([]);
  const [approvals, setApprovals] = useState<SandboxApproval[]>([]);
  const [executions, setExecutions] = useState<SandboxExecution[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<SandboxTarget | null>(null);
  const [preflight, setPreflight] = useState<SandboxPreflightResult | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  // Create sandbox target
  const [form, setForm] = useState({
    provider: 'aws', accountId: '', region: 'us-east-1',
    services: 's3', estimatedMaxCost: '0.01', costCeiling: '0.10', ttlHours: '1',
  });

  useEffect(() => { loadTargets(); }, []);

  async function loadTargets() {
    try {
      // Sandbox targets are managed via the sandbox API
      setTargets([]);
    } catch { /* sandbox API may not be running */ }
  }

  async function createTarget() {
    setLoading(true);
    try {
      const r = await api('/api/v1/sandbox/targets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: form.provider,
          accountId: form.accountId,
          region: form.region,
          services: form.services.split(',').map(s => s.trim()),
          estimatedMaxCost: parseFloat(form.estimatedMaxCost),
          costCeiling: parseFloat(form.costCeiling),
          ttlHours: parseFloat(form.ttlHours),
        }),
      });
      setSelectedTarget(r.sandboxTarget);
      setMessage('Sandbox target created.');
      loadTargets();
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    }
    setLoading(false);
  }

  async function verifyIdentity(targetId: string) {
    setLoading(true);
    try {
      const r = await api(`/api/v1/sandbox/targets/${targetId}/verify-identity`, { method: 'POST' });
      if (r.verified) {
        setMessage(`Identity verified: account ${r.accountId}`);
      } else {
        setMessage(`Identity NOT verified: ${r.note || 'No credentials'}`);
      }
      loadTargets();
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    }
    setLoading(false);
  }

  async function runPreflight(targetId: string, planChecksum: string, packageChecksum: string) {
    setLoading(true);
    try {
      const r = await api('/api/v1/sandbox/preflight', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ packageId: 'ui-test', sandboxTargetId: targetId, planChecksum, packageChecksum }),
      });
      setPreflight(r.preflight);
      setMessage(r.canProceed ? 'Preflight PASSED' : 'Preflight FAILED');
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    }
    setLoading(false);
  }

  // ═══════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════
  return (
    <div style={{ padding: '20px 24px', maxWidth: 1000, margin: '0 auto', color: '#e5e7eb', fontFamily: 'system-ui, sans-serif' }}>
      <h2 style={{ margin: '0 0 6px', fontSize: 22 }}>🛡️ Sandbox Execution</h2>
      <p style={{ margin: '0 0 20px', color: '#9ca3af', fontSize: 13 }}>
        Controlled cloud execution with explicit safety gates.
        <span style={{ color: '#ef4444', fontWeight: 600, marginLeft: 8 }}>
          ⚠ Real cloud resources may be created.
        </span>
      </p>

      {/* Fidelity legend */}
      <div style={{ marginBottom: 20, padding: 10, background: '#111827', borderRadius: 6, display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12 }}>
        {(['PLAN_ONLY', 'SIMULATED', 'LOCAL_RUNTIME', 'SANDBOX', 'CONTROLLED_REAL', 'PRODUCTION'] as ExecutionFidelity[]).map(fid => (
          <FidelityBadge key={fid} fid={fid} />
        ))}
      </div>

      {message && (
        <div style={{ padding: '8px 14px', marginBottom: 16, background: message.includes('Error') ? '#7f1d1d' : '#065f46', borderRadius: 6, fontSize: 13 }}>
          {message}
        </div>
      )}

      {/* ── Create Sandbox Target ── */}
      <Section title="📋 Sandbox Target">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div>
            <label style={{ fontSize: 12, color: '#9ca3af' }}>AWS Account ID</label>
            <input value={form.accountId} onChange={e => setForm({ ...form, accountId: e.target.value })}
              placeholder="123456789012"
              style={inputStyle} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#9ca3af' }}>Region</label>
            <input value={form.region} onChange={e => setForm({ ...form, region: e.target.value })}
              style={inputStyle} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#9ca3af' }}>Services (comma-separated)</label>
            <input value={form.services} onChange={e => setForm({ ...form, services: e.target.value })}
              style={inputStyle} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#9ca3af' }}>TTL (hours)</label>
            <input value={form.ttlHours} onChange={e => setForm({ ...form, ttlHours: e.target.value })}
              style={inputStyle} type="number" min="0.5" max="24" step="0.5" />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#9ca3af' }}>Est. Max Cost (USD)</label>
            <input value={form.estimatedMaxCost} onChange={e => setForm({ ...form, estimatedMaxCost: e.target.value })}
              style={inputStyle} type="number" min="0" step="0.01" />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#9ca3af' }}>Cost Ceiling (USD)</label>
            <input value={form.costCeiling} onChange={e => setForm({ ...form, costCeiling: e.target.value })}
              style={inputStyle} type="number" min="0" step="0.01" />
          </div>
        </div>
        <button onClick={createTarget} disabled={loading || !form.accountId}
          style={{
            marginTop: 12, padding: '8px 20px', background: loading ? '#374151' : '#dc2626',
            color: '#fff', border: 'none', borderRadius: 6, fontWeight: 600, cursor: 'pointer', fontSize: 14,
          }}>
          {loading ? '...' : 'Create Sandbox Target'}
        </button>
        <span style={{ marginLeft: 12, fontSize: 12, color: '#ef4444' }}>
          ⚠ This creates a LOCAL control-plane record only. No AWS resources.
        </span>
      </Section>

      {/* ── Selected Target Details ── */}
      {selectedTarget && (
        <Section title={`🎯 Target: ${selectedTarget.sandboxTargetId}`}>
          <Row label="Provider" value={selectedTarget.provider.toUpperCase()} />
          <Row label="Account" value={selectedTarget.account.accountId} />
          <Row label="Region" value={selectedTarget.region} />
          <Row label="Services" value={selectedTarget.resourceAllowlist.services.join(', ')} />
          <Row label="TTL" value={`${selectedTarget.ttlHours}h`} />
          <Row label="Est. Max Cost" value={`$${selectedTarget.costEstimate.estimatedMaximumCost.toFixed(2)}`} />
          <Row label="Cost Ceiling" value={`$${selectedTarget.costEstimate.ceiling.toFixed(2)}`} color={selectedTarget.costEstimate.estimatedMaximumCost > selectedTarget.costEstimate.ceiling ? '#ef4444' : '#10b981'} />
          <Row label="Production" value={selectedTarget.production ? '⚠ YES' : 'No'} color={selectedTarget.production ? '#ef4444' : '#10b981'} />
          <Row label="Account Verified" value={selectedTarget.account.verified ? '✅ Yes' : '❌ No'} color={selectedTarget.account.verified ? '#10b981' : '#ef4444'} />

          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={() => verifyIdentity(selectedTarget.sandboxTargetId)} disabled={loading}
              style={btnStyle('#3b82f6')}>
              Verify AWS Identity
            </button>
            <button onClick={() => runPreflight(selectedTarget.sandboxTargetId, 'test-plan-cs', 'test-pkg-cs')} disabled={loading}
              style={btnStyle('#8b5cf6')}>
              Run Sandbox Preflight
            </button>
            <button disabled style={btnStyle('#dc2626', true)}>
              🚫 CONTROLLED REAL
            </button>
            <button disabled style={btnStyle('#991b1b', true)}>
              🚫 PRODUCTION
            </button>
          </div>
        </Section>
      )}

      {/* ── Preflight Results ── */}
      {preflight && (
        <Section title={`🔍 Preflight: ${preflight.allPassed ? '✅ PASSED' : '❌ FAILED'}`}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            {Object.entries(preflight.checks).map(([key, val]) => (
              <div key={key} style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '2px 6px', background: val ? '#065f46' : '#7f1d1d', borderRadius: 3 }}>
                <span>{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                <span>{val ? '✅' : '❌'}</span>
              </div>
            ))}
          </div>
          {preflight.failures.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#fca5a5' }}>
              Failures: {preflight.failures.join(', ')}
            </div>
          )}
        </Section>
      )}

      {/* ── AIRLOCK Approval Warning ── */}
      <Section title="🔒 AIRLOCK Approval Required">
        <div style={{ padding: 12, background: '#7f1d1d', borderRadius: 6, fontSize: 13 }}>
          <strong>⚠ THIS CREATES REAL CLOUD RESOURCES</strong>
          <p style={{ margin: '8px 0 0', color: '#fca5a5' }}>
            Before real AWS S3 bucket creation, you must explicitly approve:
          </p>
          <ul style={{ margin: '4px 0 0', paddingLeft: 20, color: '#fca5a5', fontSize: 12 }}>
            <li>AWS Account identity</li>
            <li>Target region</li>
            <li>Resource scope (S3 only)</li>
            <li>Cost ceiling (USD)</li>
            <li>TTL / expiration</li>
          </ul>
          <p style={{ margin: '10px 0 0', fontWeight: 700 }}>
            SANDBOX = ASK (never AUTO). CONTROLLED_REAL = BLOCKED. PRODUCTION = BLOCKED.
          </p>
        </div>
        <button disabled
          style={{
            marginTop: 12, padding: '10px 24px', background: '#374151', color: '#9ca3af',
            border: 'none', borderRadius: 6, fontWeight: 700, fontSize: 15, cursor: 'not-allowed',
          }}>
          Approve Sandbox Execution (requires preflight PASS)
        </button>
      </Section>

      {/* ── Execution Timeline ── */}
      <Section title="⏱ Execution Stages">
        {[
          'PREFLIGHT', 'IDENTITY', 'POLICY', 'APPROVAL',
          'EXECUTION', 'OBSERVATION', 'VALIDATION',
          'VERIFICATION', 'CLEANUP', 'POST-CLEANUP',
        ].map((stage, i) => (
          <div key={stage} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0',
            fontSize: 13, color: '#9ca3af',
          }}>
            <span style={{ width: 24, height: 24, borderRadius: '50%', background: '#374151',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: '#6b7280' }}>
              {i + 1}
            </span>
            <span>{stage.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </Section>
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '6px 10px', background: '#111827',
  border: '1px solid #374151', borderRadius: 4, color: '#e5e7eb',
  fontSize: 13, boxSizing: 'border-box',
};

function btnStyle(bg: string, disabled = false): React.CSSProperties {
  return {
    padding: '7px 14px', background: disabled ? '#374151' : bg,
    color: disabled ? '#6b7280' : '#fff', border: 'none', borderRadius: 5,
    fontWeight: 600, fontSize: 13, cursor: disabled ? 'not-allowed' : 'pointer',
  };
}
