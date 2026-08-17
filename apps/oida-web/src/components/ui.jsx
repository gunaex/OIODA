import { Link } from "react-router-dom";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";

export function Badge({ children, tone = "gray" }) {
  const tones = {
    gray: "bg-gray-100 text-gray-600",
    green: "bg-emerald-100 text-emerald-700",
    blue: "bg-sky-100 text-sky-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-rose-100 text-rose-700",
    violet: "bg-violet-100 text-violet-700",
  };
  return <span className={`badge ${tones[tone] || tones.gray}`}>{children}</span>;
}

export function statusTone(status) {
  const s = (status || "").toLowerCase();
  if (["confirmed", "done", "passed", "completed", "active", "approved", "inprogress"].includes(s)) return "green";
  if (["in_progress", "executing", "inreview", "ready", "published"].includes(s)) return "blue";
  if (["blocked", "failed", "rejected", "superseded", "archived", "closed"].includes(s)) return "red";
  if (["draft", "todo", "not_run", "received", "open", "pending"].includes(s)) return "amber";
  return "gray";
}

export function StatusBadge({ status }) {
  const label = (status || "—").replaceAll("_", " ");
  return <Badge tone={statusTone(status)}>{label}</Badge>;
}

export function Card({ children, className = "" }) {
  return <div className={`oida-card ${className}`}>{children}</div>;
}

export function CardHeader({ title, subtitle, right }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-gray-100 px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function StatCard({ label, value, sub, tone = "gray" }) {
  const tones = {
    gray: "text-gray-900",
    green: "text-emerald-700",
    blue: "text-sky-700",
    amber: "text-amber-700",
    red: "text-rose-700",
  };
  return (
    <div className="oida-card px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${tones[tone] || tones.gray}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

export function SectionTitle({ children, right }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-sm font-semibold text-gray-700">{children}</h3>
      {right}
    </div>
  );
}

export function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
      <RefreshCw size={16} className="animate-spin" /> Loading…
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="oida-card flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <Inbox size={28} className="text-gray-300" />
      <div className="text-sm font-semibold text-gray-700">{title}</div>
      {children && <div className="text-xs text-gray-500">{children}</div>}
    </div>
  );
}

export function OidaError({ title = "Oops!…I Did It Again.", message, onRetry, details }) {
  return (
    <div className="oida-card mx-auto mt-8 max-w-lg px-6 py-10 text-center">
      <AlertTriangle size={30} className="mx-auto text-amber-500" />
      <h2 className="mt-3 text-base font-semibold text-gray-800">{title}</h2>
      <p className="mt-2 text-sm text-gray-600">{message || "Something didn't go as planned. Your work is safe."}</p>
      <div className="mt-5 flex items-center justify-center gap-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded-lg border border-gray-300 bg-gray-100 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200"
          >
            Retry
          </button>
        )}
        {details && (
          <details className="text-left">
            <summary className="cursor-pointer text-sm text-gray-500">View Details</summary>
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-gray-50 p-3 text-xs text-gray-600">{details}</pre>
          </details>
        )}
      </div>
    </div>
  );
}

export function SignInPrompt({ service, children }) {
  return (
    <div className="oida-card mx-auto mt-6 max-w-md px-6 py-10 text-center">
      <h2 className="text-base font-semibold text-gray-800">Sign in to connect {service}</h2>
      <p className="mt-2 text-sm text-gray-600">
        {children || `This view reads from ${service}. Sign in once and the whole workspace connects.`}
      </p>
      <Link
        to="/login"
        className="mt-4 inline-block rounded-lg border border-gray-300 bg-gray-100 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200"
      >
        Sign in
      </Link>
    </div>
  );
}

export function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Table({ head, children }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} className="oida-th">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Tr({ children, onClick, className = "" }) {
  return (
    <tr onClick={onClick} className={`hover:bg-gray-50 ${className}`}>
      {children}
    </tr>
  );
}

export function Td({ children, className = "" }) {
  return <td className={`oida-td ${className}`}>{children}</td>;
}

export function LinkButton({ to, children, tone = "primary" }) {
  const tones = {
    primary: "border border-gray-300 bg-gray-100 text-gray-900 hover:bg-gray-200",
    ghost: "border border-gray-300 text-gray-700 hover:bg-gray-50",
  };
  return (
    <Link to={to} className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium ${tones[tone]}`}>
      {children}
    </Link>
  );
}
