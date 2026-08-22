// OIDA OS API client — routes every call to the right bounded service via the
// shell's own proxy prefixes. The proxy owns per-service session isolation
// (see vite.config.js); this client only needs to remember which service a
// resource belongs to.

export const SERVICES = ["da", "pm", "qa", "conductor", "account"];

// Production API base (gateway). Empty in local dev → relative /api/* (Vite proxy).
// Set VITE_API_BASE=https://api-oida.kanphong.com for production builds.
export function resolveApiBase(configured, hostname) {
  const explicit = String(configured || "").replace(/\/+$/, "");
  if (explicit) return explicit;
  // Production must never send API calls to the static Pages origin. Keep
  // local/preview builds relative so Vite's bounded-service proxy still works.
  return hostname === "oida.kanphong.com" ? "https://api-oida.kanphong.com" : "";
}

export const API_BASE = resolveApiBase(
  import.meta.env?.VITE_API_BASE,
  globalThis.location?.hostname
);

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function request(service, path, options = {}) {
  const url = `${API_BASE}/api/${service}${path}`;
  const opts = {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "include",
    ...options,
  };
  if (opts.body && typeof opts.body !== "string") {
    opts.body = JSON.stringify(opts.body);
  }

  // Ecosystem SSO: attach the single Account Again identity token to every
  // service call. The gateway requires it on all protected routes and derives
  // a trusted actor context from it. No password is ever sent downstream.
  const ecoToken = localStorage.getItem("oida_ecosystem_token");
  if (ecoToken) {
    opts.headers = { ...(opts.headers || {}) };
    if (!opts.headers.Authorization && !opts.headers.authorization) {
      opts.headers.Authorization = `Bearer ${ecoToken}`;
    }
  }

  const res = await fetch(url, opts);
  if (res.status === 204) return null;

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson
    ? await res.json().catch(() => null)
    : await res.text().catch(() => null);

  // A static host returning the SPA shell with HTTP 200 is not API success.
  // Reject it before auth/project code can mistake HTML for trusted data.
  if (res.ok && !isJson) {
    throw new ApiError("Unexpected non-JSON response from the API", 502, null);
  }

  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message)) || data || `HTTP ${res.status}`;
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status, data);
  }
  return data;
}

export const get = (service, path) => request(service, path);
export const post = (service, path, body) => request(service, path, { method: "POST", body });
export const put = (service, path, body) => request(service, path, { method: "PUT", body });
export const patch = (service, path, body) => request(service, path, { method: "PATCH", body });
export const del = (service, path) => request(service, path, { method: "DELETE" });
