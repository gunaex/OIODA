const base = "/api";

async function request(path, options = {}) {
  const res = await fetch(base + path, {
    headers: {
      "Content-Type": "application/json",
      "X-Actor": localStorage.getItem("da-actor") || "local-user",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* keep status */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: (p, body) => request(p, { method: "PUT", body: JSON.stringify(body) }),
};
