import { useEffect, useState } from 'react';
import { GitBranch, Plus, Rocket, ShieldCheck, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import {
  listIntents, createIntent, createRun, getRun,
  dispatchEngineering, dispatchInfrastructure, dispatchQA, computeReadiness,
} from '../api/client';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';

// Real orchestration operator surface (E8-G). Every value on this page comes from a
// live call to /api/orchestration/* — there is no mock/sample data here.

function AdapterTag({ status }) {
  const styles = {
    REAL_RUNTIME: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    FROZEN_RUNTIME: 'bg-blue-50 text-blue-700 border-blue-200',
    HARNESS: 'bg-amber-50 text-amber-700 border-amber-200',
    UNAVAILABLE: 'bg-gray-100 text-gray-500 border-gray-200',
  };
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-md text-[11px] font-mono border ${styles[status] || styles.UNAVAILABLE}`}>
      {status}
    </span>
  );
}

export default function OrchestrationPage({ slug }) {
  const [loading, setLoading] = useState(true);
  const [intents, setIntents] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [busy, setBusy] = useState(false);

  // New intent form
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const refresh = () => listIntents().then(setIntents).catch(() => toast.error('Failed to load business intents'));

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, []);

  const handleCreateIntent = async (e) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setBusy(true);
    try {
      const intent = await createIntent({ title, description, priority: 'HIGH', project_slug: slug });
      const run = await createRun(intent.businessIntentId, {
        assignments: { engineering: true, infrastructure: true, qa: true },
      });
      toast.success(`Delivery run ${run.runId} created`);
      setTitle('');
      setDescription('');
      await refresh();
      setSelectedRun(await getRun(run.runId));
    } catch (err) {
      toast.error(err.response?.data?.detail?.error || 'Failed to create business intent');
    } finally {
      setBusy(false);
    }
  };

  const advance = async (action) => {
    if (!selectedRun) return;
    setBusy(true);
    try {
      if (action === 'engineering') {
        await dispatchEngineering(selectedRun.runId, {
          requirements: 'Add a GET /healthz endpoint returning {status: ok}',
          project_name: slug,
        });
      } else if (action === 'infrastructure') {
        await dispatchInfrastructure(selectedRun.runId);
      } else if (action === 'qa') {
        await dispatchQA(selectedRun.runId);
      } else if (action === 'readiness') {
        await computeReadiness(selectedRun.runId);
      }
      setSelectedRun(await getRun(selectedRun.runId));
      toast.success('Updated');
    } catch (err) {
      toast.error(err.response?.data?.detail || err.response?.data?.detail?.error || 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="p-8 text-sm text-gray-500">Loading orchestration state…</div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <GitBranch size={18} /> Delivery Orchestration
          </h2>
          <p className="text-sm text-gray-500">Real BusinessIntent → DeliveryRun → specialist dispatch → readiness.</p>
        </div>
        <button onClick={refresh} className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <form onSubmit={handleCreateIntent} className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            placeholder="Business intent title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 disabled:opacity-50"
        >
          <Plus size={14} /> Submit Business Intent & Start Run
        </button>
      </form>

      {intents.length === 0 ? (
        <EmptyState icon={Rocket} title="No business intents yet" description="Submit one above to start real orchestration." />
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100">
          {intents.map((intent) => (
            <div key={intent.businessIntentId} className="p-4 flex items-center justify-between">
              <div>
                <div className="font-medium text-gray-900">{intent.title}</div>
                <div className="text-xs text-gray-500">{intent.businessIntentId} · correlation {intent.correlationId}</div>
              </div>
              <StatusBadge status={intent.status?.toLowerCase() || 'draft'} />
            </div>
          ))}
        </div>
      )}

      {selectedRun && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold text-gray-900">Run {selectedRun.runId}</div>
              <div className="text-xs text-gray-500">Stage: {selectedRun.currentStage} · Status: {selectedRun.status}</div>
            </div>
            <ShieldCheck size={18} className="text-gray-400" />
          </div>

          <div className="flex gap-2 flex-wrap">
            <button onClick={() => advance('engineering')} disabled={busy} className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 hover:bg-gray-50">
              Dispatch Engineering
            </button>
            <button onClick={() => advance('infrastructure')} disabled={busy} className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 hover:bg-gray-50">
              Dispatch Infrastructure
            </button>
            <button onClick={() => advance('qa')} disabled={busy} className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 hover:bg-gray-50">
              Dispatch QA
            </button>
            <button onClick={() => advance('readiness')} disabled={busy} className="px-3 py-1.5 text-sm rounded-lg bg-gray-900 text-white hover:bg-gray-800">
              Compute Readiness
            </button>
          </div>

          {selectedRun.dispatches?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase mb-2">Specialist Dispatches</div>
              <div className="space-y-1.5">
                {selectedRun.dispatches.map((d, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="w-32 text-gray-600">{d.specialist}</span>
                    <AdapterTag status={d.adapterStatus} />
                    <span className="text-gray-400">{d.dispatchStatus}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedRun.readinessDecisions?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase mb-2">Delivery Readiness</div>
              {selectedRun.readinessDecisions.map((r, i) => (
                <div key={i} className="text-sm">
                  <StatusBadge status={r.decision === 'READY_FOR_DELIVERY' ? 'approved' : 'change_proposed'} />{' '}
                  <span className="ml-2 text-gray-600">{r.reasonCode}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
