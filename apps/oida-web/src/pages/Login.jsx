import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Boxes } from "lucide-react";
import { Badge } from "../components/ui";

function sanitizeReturnTo(raw) {
  if (!raw) return "/projects";
  let decoded;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return "/projects";
  }
  // Only allow same-origin absolute paths — never "//evil.com" or "https://".
  if (!decoded.startsWith("/") || decoded.startsWith("//") || decoded.includes("://")) {
    return "/projects";
  }
  return decoded;
}

export default function Login() {
  const { login, lastLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = sanitizeReturnTo(new URLSearchParams(location.search).get("returnTo"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const results = await login(email, password);
      if (results.account && results.account.ok === false) {
        setError("Sign-in did not succeed. Check your credentials.");
      } else if (results.mustChangePassword) {
        navigate("/change-password", { replace: true });
      } else {
        navigate(returnTo, { replace: true });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <Boxes size={34} className="text-gray-900" />
          <h1 className="mt-3 text-2xl font-bold tracking-tight">OIDA OS</h1>
          <p className="text-sm text-gray-500">Oops!…I Did It Again — Project Delivery Workspace</p>
        </div>

        <form onSubmit={submit} className="oida-card space-y-4 p-6">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
            />
          </div>

          {error && <p className="text-sm text-rose-600">{error}</p>}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg border border-gray-300 bg-gray-100 px-4 py-2.5 text-sm font-medium text-gray-900 hover:bg-gray-200 disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>

          {lastLogin && (
            <div className="space-y-1 border-t border-gray-100 pt-3">
              <div className="text-[0.7rem] font-semibold uppercase tracking-wide text-gray-400">
                Connected services
              </div>
              {Object.entries(lastLogin).map(([svc, r]) => (
                <div key={svc} className="flex items-center justify-between text-xs">
                  <span className="text-gray-600">{svc}</span>
                  {r.ok ? (
                    <Badge tone="green">connected</Badge>
                  ) : (
                    <Badge tone="amber">unavailable — {r.error}</Badge>
                  )}
                </div>
              ))}
              {lastLogin.qa?.ok && (
                <p className="pt-1 text-xs text-emerald-600">
                  Ready. Opening your projects…
                </p>
              )}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
