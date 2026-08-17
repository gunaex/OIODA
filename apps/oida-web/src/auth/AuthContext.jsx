import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { request } from "../api/client";
import { accountApi } from "../api";

const AuthContext = createContext(null);

// Services the owner needs for normal project work. Document Again runs in
// local mode (actor header, no password). PM / QA / Conductor each accept the
// SAME ecosystem identity (Account Again) — one sign-in federates to all of
// them. Local per-service sessions remain for standalone use.
const HUMAN_SERVICES = ["pm", "qa", "conductor"];
const ECO_TOKEN_KEY = "oida_ecosystem_token";

export function AuthProvider({ children }) {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [identity, setIdentity] = useState(null);
  const [session, setSession] = useState({ da: { available: true, actor: getActor() } });
  const [lastLogin, setLastLogin] = useState(null);
  const [ecosystem, setEcosystem] = useState(() => {
    const t = localStorage.getItem(ECO_TOKEN_KEY);
    return t ? { accessToken: t } : null;
  });

  // Bootstrap: a stored token is only valid if the gateway accepts it. Never
  // trust localStorage alone — validate the token against /api/auth/me before
  // declaring the user AUTHENTICATED.
  const bootstrap = useCallback(async () => {
    const token = localStorage.getItem(ECO_TOKEN_KEY);
    if (!token) {
      setAuthenticated(false);
      setIdentity(null);
      setLoading(false);
      return;
    }
    try {
      const me = await request("auth", "/me");
      setAuthenticated(true);
      setIdentity(me);
      setEcosystem({ accessToken: token });
    } catch {
      localStorage.removeItem(ECO_TOKEN_KEY);
      setEcosystem(null);
      setAuthenticated(false);
      setIdentity(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const probe = useCallback(async () => {
    const next = { da: { available: true, actor: getActor() } };
    await Promise.all(
      HUMAN_SERVICES.map(async (svc) => {
        try {
          const user = await request(svc, "/auth/me");
          next[svc] = { user };
        } catch {
          next[svc] = null;
        }
      })
    );
    setSession(next);
  }, []);

  useEffect(() => {
    if (authenticated) probe();
  }, [authenticated, probe]);

  const login = useCallback(async (email, password) => {
    // Single sign-on: authenticate ONCE against Account Again, store the
    // signed ecosystem identity token, and verify the bounded services accept
    // it. No per-service passwords are ever sent.
    try {
      const eco = await accountApi.ecosystemToken(email, password);
      localStorage.setItem(ECO_TOKEN_KEY, eco.accessToken);
      setEcosystem(eco);
      setAuthenticated(true);
    } catch (err) {
      setLastLogin({ account: { ok: false, error: err.message || String(err) } });
      return { account: { ok: false, error: err.message || String(err) } };
    }

    try {
      const me = await request("auth", "/me");
      setIdentity(me);
    } catch {
      setIdentity(null);
    }

    const results = {};
    await Promise.all(
      HUMAN_SERVICES.map(async (svc) => {
        try {
          const user = await request(svc, "/auth/me");
          results[svc] = { ok: true, user };
        } catch (err) {
          results[svc] = { ok: false, error: err.message };
        }
      })
    );
    const next = { da: { available: true, actor: getActor() } };
    for (const svc of HUMAN_SERVICES) {
      if (results[svc].ok) next[svc] = { user: results[svc].user };
      else next[svc] = null;
    }
    setSession(next);
    setLastLogin(results);
    return results;
  }, []);

  const logout = useCallback(async () => {
    // End the usable OIDA session: drop the ecosystem token. Best-effort
    // standalone-cookie logout is attempted for services that may hold one.
    await Promise.all(
      HUMAN_SERVICES.map((svc) =>
        request(svc, "/auth/logout", { method: "POST" }).catch(() => null)
      )
    );
    localStorage.removeItem(ECO_TOKEN_KEY);
    setEcosystem(null);
    setAuthenticated(false);
    setIdentity(null);
    setSession({ da: { available: true, actor: getActor() } });
  }, []);

  const setActor = useCallback((actor) => {
    localStorage.setItem("oida-actor", actor);
    setSession((s) => ({ ...s, da: { available: true, actor } }));
  }, []);

  const loggedIn = HUMAN_SERVICES.filter((svc) => session[svc] && session[svc].user);

  return (
    <AuthContext.Provider
      value={{
        loading,
        authenticated,
        identity,
        session,
        loggedIn,
        login,
        logout,
        setActor,
        lastLogin,
        ecosystem,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function getActor() {
  return localStorage.getItem("oida-actor") || "Owner";
}
