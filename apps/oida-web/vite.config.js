import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// OIDA OS shell — unified entry point over the AGAIN Ecosystem.
//
// Each bounded service is exposed under its own /api/<service> prefix and
// proxied to its own backend origin. Because every service issues the SAME
// httpOnly cookie names (`access_token`, `refresh_token`), the proxy renames
// the Set-Cookie on the way back (oida_<service>_at / oida_<service>_rt) and
// converts them back into an Authorization: Bearer header (or Cookie header
// for /auth/refresh) on the way in. This keeps each service's session fully
// isolated under the single shell origin — no cookie collisions, no CORS
// changes, no shared database.

const SERVICES = {
  da: { target: "http://localhost:8003", upstreamBase: "/api" },
  pm: { target: "http://localhost:8000", upstreamBase: "/api" },
  qa: { target: "http://localhost:8002", upstreamBase: "/api" },
  conductor: { target: "http://localhost:8010", upstreamBase: "/api" },
  account: { target: "http://localhost:8011", upstreamBase: "/api/v1" },
  infra: { target: "http://localhost:18090", upstreamBase: "/api/v1" },
};

function parseCookies(header) {
  const out = {};
  if (!header) return out;
  for (const part of header.split(";")) {
    const idx = part.indexOf("=");
    if (idx === -1) continue;
    out[part.slice(0, idx).trim()] = part.slice(idx + 1).trim();
  }
  return out;
}

function buildProxyRule(svc, { target, upstreamBase }) {
  const prefix = `/api/${svc}`;
  return {
    [prefix]: {
      target,
      changeOrigin: true,
      rewrite: (path) => {
        const rest = path.slice(prefix.length) || "/";
        return upstreamBase + rest;
      },
      configure(proxy) {
        proxy.on("proxyReq", (proxyReq, req) => {
          const cookies = parseCookies(req.headers && req.headers.cookie);
          const access = cookies[`oida_${svc}_at`];
          const refresh = cookies[`oida_${svc}_rt`];

          // Never leak the shell's per-service cookies upstream.
          proxyReq.removeHeader("cookie");

          const upstreamPath = proxyReq.path || "";
          const isRefresh = upstreamPath.includes("/auth/refresh");
          const isLogout = upstreamPath.includes("/auth/logout");

          // Ecosystem SSO: the browser carries the single Account Again
          // identity token as Authorization — forward it verbatim. Otherwise
          // fall back to the per-service session cookie (standalone mode).
          const clientAuth = req.headers && (req.headers.authorization || req.headers.Authorization);
          if (clientAuth && !isRefresh && !isLogout) {
            proxyReq.setHeader("authorization", clientAuth);
          } else if (isRefresh || isLogout) {
            // These endpoints read the cookies directly, not the Bearer.
            if (access || refresh) {
              proxyReq.setHeader(
                "cookie",
                [access && `access_token=${access}`, refresh && `refresh_token=${refresh}`]
                  .filter(Boolean)
                  .join("; ")
              );
            }
          } else if (access) {
            proxyReq.setHeader("authorization", `Bearer ${access}`);
          }

          // Document Again (local mode) uses an actor header, not a token.
          // Prefer whatever the client already sent (e.g. X-Actor), else fall
          // back to the oida_actor cookie or the default local actor.
          if (svc === "da" && !(req.headers && req.headers["x-actor"])) {
            proxyReq.setHeader("x-actor", cookies.oida_actor || "local-user");
          }
        });

        proxy.on("proxyRes", (proxyRes) => {
          const setCookies = proxyRes.headers["set-cookie"];
          if (setCookies && setCookies.length) {
            proxyRes.headers["set-cookie"] = setCookies.map((line) => {
              let l = line;
              if (l.startsWith("access_token=")) {
                l = l.replace(/^access_token=/, `oida_${svc}_at=`);
                l = l.replace(/; path=\/[^;]*/i, "; path=/");
              } else if (l.startsWith("refresh_token=")) {
                l = l.replace(/^refresh_token=/, `oida_${svc}_rt=`);
                l = l.replace(/; path=\/[^;]*/i, "; path=/");
              }
              return l;
            });
          }
        });
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5190,
    proxy: Object.assign(
      {},
      ...Object.entries(SERVICES).map(([svc, cfg]) => buildProxyRule(svc, cfg))
    ),
  },
});
