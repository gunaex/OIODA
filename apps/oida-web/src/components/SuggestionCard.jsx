import { useState } from "react";
import { documentApi } from "../api";
import { Badge } from "./ui";

const SEV_TONE = { HIGH: "red", MEDIUM: "amber", LOW: "gray" };

export default function SuggestionCard({ suggestion, onChanged }) {
  const [answer, setAnswer] = useState("");
  const [source, setSource] = useState("CUSTOMER");
  const [s, setS] = useState(suggestion);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submitAnswer() {
    if (!answer.trim()) return;
    setBusy(true); setError(null);
    try {
      setS(await documentApi.answerSuggestion(s.id, answer, source));
      setS(await documentApi.interpretSuggestion(s.id));
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function review(decision) {
    setBusy(true); setError(null);
    try {
      const updated = await documentApi.reviewSuggestion(s.id, decision);
      setS(updated);
      onChanged?.(updated);
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  const tone = SEV_TONE[s.severity] || "gray";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">OIDA Suggestion</span>
            {s.severity && <Badge tone={tone}>{s.severity}</Badge>}
            <Badge tone="gray">{s.status}</Badge>
          </div>
          <div className="mt-1 text-sm font-semibold text-gray-900">{s.title}</div>
        </div>
      </div>

      {s.description && <p className="mt-1 text-xs text-gray-600">{s.description}</p>}

      {s.why_it_matters && (
        <div className="mt-2 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700">
          <span className="font-semibold">Why this matters: </span>{s.why_it_matters}
        </div>
      )}

      {s.question && !s.answer && (
        <div className="mt-3">
          <div className="text-xs font-medium text-gray-700">Question: <span className="font-normal">{s.question}</span></div>
          <div className="mt-2 flex items-center gap-2">
            <input className="input flex-1" placeholder="Customer answer" value={answer} onChange={(e) => setAnswer(e.target.value)} />
            <select className="input !w-32" value={source} onChange={(e) => setSource(e.target.value)}>
              {["CUSTOMER", "PROJECT_OWNER", "ARCHITECT", "PM", "QA", "INFRA", "OTHER"].map((x) => <option key={x}>{x}</option>)}
            </select>
            <button onClick={submitAnswer} disabled={busy || !answer.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">
              Submit Answer
            </button>
          </div>
        </div>
      )}

      {s.answer && (
        <div className="mt-3 space-y-2 text-xs">
          <div className="rounded-lg bg-sky-50 px-3 py-2">
            <span className="font-semibold text-sky-700">Customer Answer: </span>
            <span className="text-gray-800">{s.answer}</span>
            <span className="text-gray-400"> · {s.answer_source}</span>
          </div>

          {s.interpretation && (
            <div className="rounded-lg border border-gray-100 px-3 py-2">
              <div className="font-semibold text-gray-700">OIDA Interpretation {s.interpretation_confidence && <Badge tone="blue">{s.interpretation_confidence}</Badge>}</div>
              <div className="mt-0.5 text-gray-700">{s.interpretation}</div>
            </div>
          )}

          {s.follow_up && (
            <div className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
              <span className="font-semibold">Follow-up: </span>{s.follow_up}
            </div>
          )}

          {s.proposed_update && !s.review_decision && (
            <div className="rounded-lg border border-gray-200 px-3 py-2">
              <div className="font-semibold text-gray-700">Proposed Update</div>
              <div className="mt-0.5 text-gray-600">{s.proposed_update.text || s.proposed_update.kind}</div>
              <div className="mt-0.5 text-[10px] text-gray-400">{s.proposed_update.note}</div>
              <div className="mt-2 flex gap-2">
                <button onClick={() => review("ACCEPTED")} disabled={busy} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700">Accept Proposed Update</button>
                <button onClick={() => review("REJECTED")} disabled={busy} className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50">Reject</button>
              </div>
            </div>
          )}

          {s.review_decision && (
            <div className="rounded-lg bg-gray-50 px-3 py-2">
              <span className="font-semibold text-gray-700">Decision: </span>
              <Badge tone={s.review_decision === "ACCEPTED" ? "green" : "red"}>{s.review_decision}</Badge>
              {s.applied?.length > 0 && <span className="ml-1 text-gray-500">· applied {s.applied.map((a) => a.id).join(", ")}</span>}
            </div>
          )}
        </div>
      )}

      {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
    </div>
  );
}
