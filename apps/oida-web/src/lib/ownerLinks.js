function safeBase(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href.replace(/\/$/, "")
      : null;
  } catch {
    return null;
  }
}

export function buildOwnerLinks(truth, config = {}) {
  if (!config.authContinuity) return { pm: null, qa: null, infra: null };
  const pmBase = safeBase(config.pmBase);
  const qaBase = safeBase(config.qaBase);
  const pmId = truth?.bindings?.pm?.binding_status === "BOUND"
    ? truth.bindings.pm.external_project_id : null;
  const qaBinding = (truth?.bindings?.qa || []).find(
    (row) => row.binding_status === "BOUND" && row.external_project_id
  );
  // Infra Again currently has no stable URL route that accepts a design ID.
  return {
    pm: pmBase && pmId ? `${pmBase}/${encodeURIComponent(pmId)}/gantt` : null,
    qa: qaBase && qaBinding ? `${qaBase}/${encodeURIComponent(qaBinding.external_project_id)}/dashboard` : null,
    infra: null,
  };
}
