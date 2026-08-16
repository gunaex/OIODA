// OIDA OS API client — routes every call to the right bounded service via the
// shell's own proxy prefixes. The proxy owns per-service session isolation
// (see vite.config.js); this client only needs to remember which service a
// resource belongs to.

export const SERVICES = ["da", "pm", "qa", "conductor", "account"];

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function request(service, path, options = {}) {
  const url = `/api/${service}${path}`;
  const opts = {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "include",
    ...options,
  };
  if (opts.body && typeof opts.body !== "string") {
    opts.body = JSON.stringify(opts.body);
  }

  // Ecosystem SSO: attach the single Account Again identity token to the
  // bounded human services. The Vite proxy forwards it as Authorization:
  // Bearer upstream. No password is ever sent downstream.
  const ecoToken = localStorage.getItem("oida_ecosystem_token");
  if (ecoToken && ["pm", "qa", "conductor", "infra"].includes(service)) {
    opts.headers = { ...(opts.headers || {}) };
    if (!opts.headers.Authorization && !opts.headers.authorization) {
      opts.headers.Authorization = `Bearer ${ecoToken}`;
    }
  }

  const res = await fetch(url, opts);
  if (res.status === 204) return null;

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await res.json().catch(() => null)
    : await res.text().catch(() => null);

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
