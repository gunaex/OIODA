// OIDA R13 — Cross-service Change Request impact engine.
//
// Deterministic, no-key-safe impact intelligence. It projects LIVE truth from
// the bounded authorities (Document/PM/QA/Infra) into a per-CR impact view and
// labels every line with its provenance. It NEVER writes to any backend and
// NEVER claims an inferred line is authoritative: inferred items carry
// `relationship_type = INFERRED` and `requires_human_review = true`.
//
// Provenance vocabulary:
//   PM_RECORDED / DOCUMENT_RECORDED / QA_RECORDED / INFRA_RECORDED
//   CALCULATED  (deterministic arithmetic on recorded values)
//   AI_ESTIMATE (heuristic, no recorded value exists)
//   MANUAL_INPUT / HUMAN_OVERRIDE
//   UNKNOWN

const STOPWORDS = new Set([
  "the", "and", "for", "with", "from", "that", "this", "are", "was", "has", "have",
  "will", "should", "must", "need", "needs", "which", "what", "when", "where", "who",
  "how", "into", "onto", "over", "under", "add", "adding", "change", "changing",
  "upgrade", "increase", "increasing", "request", "requested", "requests", "customer",
  "production", "connectivity", "required", "requires", "confirm", "confirms", "support",
  "related", "existing", "current", "new", "via", "per", "can", "may", "does", "do",
]);

function tokens(text) {
  return (String(text || "").toLowerCase().match(/[a-z0-9]+/g) || [])
    .filter((w) => w.length > 2 && !STOPWORDS.has(w));
}

// Shared significant terms between CR text and a target text.
function sharedTerms(crText, targetText) {
  const a = new Set(tokens(crText));
  const b = new Set(tokens(targetText));
  return [...a].filter((w) => b.has(w));
}

function confidenceFrom(matches, total) {
  if (matches === 0) return "UNKNOWN";
  const ratio = matches / Math.max(1, total);
  if (ratio >= 0.5) return "HIGH";
  if (ratio >= 0.25) return "MEDIUM";
  return "LOW";
}

function cls(kind, matches) {
  if (matches === 0) return "UNCHANGED";
  if (matches >= 2) return "MODIFIED";
  return "MODIFIED"; // any match is treated as potentially modified, human confirms
}

function affected(crText, items, labelFn) {
  const crTerms = tokens(crText);
  const out = [];
  for (const it of items) {
    const label = labelFn(it) || "";
    const shared = sharedTerms(crText, label);
    if (shared.length === 0) continue;
    out.push({
      item: it,
      matched_terms: shared,
      relationship_type: "INFERRED",
      requires_human_review: true,
      confidence: confidenceFrom(shared.length, crTerms.length),
    });
  }
  return out;
}

export function buildCrImpact({ cr, document = {}, pm = {}, qa = {}, infra = {} }) {
  const crText = [cr?.title, cr?.requested_change, cr?.reason, cr?.notes]
    .filter(Boolean)
    .join(" ");

  // ── Function / scope impact ─────────────────────────────────────────────
  // Project functions come from PM Again (the PM truth authority). Each
  // function is UNCHANGED / MODIFIED / NEW / UNKNOWN relative to the CR text.
  const functions = pm.functions || [];
  const fnHits = affected(crText, functions, (f) => `${f.name || ""} ${f.code || ""} ${f.module || ""}`);
  // Candidate NEW functions: CR terms that name a capability no existing
  // function covers (e.g. "redundant connectivity"). Marked PROPOSED/INFERRED;
  // we do NOT invent a function record — a human must define it.
  const fnTokens = tokens(crText).filter((w) => w.length > 4 && !/gbps|mbps/.test(w));
  const fnNames = functions.map((f) => (f.name || "").toLowerCase());
  const candidateNewTerms = fnTokens.filter((w) => !fnNames.some((n) => n.includes(w))).slice(0, 5);
  const function_impact = {
    modified: fnHits.filter((h) => h.matched_terms.length > 0).map((h) => ({
      function: h.item.name || h.item.code || h.item.id,
      function_id: h.item.id,
      matched_terms: h.matched_terms,
      relationship_type: "INFERRED",
      requires_human_review: true,
      confidence: h.confidence,
      basis: "PM_RECORDED",
    })),
    new: [],
    new_candidate_terms: candidateNewTerms,
    new_note: candidateNewTerms.length
      ? "Potential NEW function(s) — human must define; evidence terms only: " + candidateNewTerms.join(", ")
      : null,
    unchanged: functions.filter((f) => !fnHits.some((h) => h.item.id === f.id)).map((f) => f.name || f.code || f.id).slice(0, 200),
    unknown: [],
    note: fnHits.length === 0
      ? "No PM function matched the CR text — scope is UNKNOWN until a human maps it."
      : null,
    confidence: fnHits.length ? "MEDIUM" : "UNKNOWN",
  };

  // ── Requirement impact ───────────────────────────────────────────────────
  const reqs = document.requirements || [];
  const reqHits = affected(crText, reqs, (r) => `${r.code} ${r.title} ${r.description || ""}`);
  const matchedReqCodes = new Set(reqHits.map((h) => h.item.code));
  const requirement_impact = {
    revised: reqHits.map((h) => ({
      code: h.item.code,
      title: h.item.title,
      current: h.item.title,
      proposed: `Revise ${h.item.code} to reflect: ${cr?.requested_change || ""}`,
      matched_terms: h.matched_terms,
      state: "PROPOSED — NOT APPLIED",
      relationship_type: "INFERRED",
      requires_human_review: true,
      confidence: h.confidence,
      basis: "DOCUMENT_RECORDED",
    })),
    new: [],
    invalidated: [],
    unresolved_clarifications: (document.clarifications || []).filter((c) => !c.resolved).map((c) => ({
      id: c.id || c.semantic_id, question: c.question,
    })),
    invalid_assumptions: (document.assumptions || []).filter((a) => sharedTerms(crText, a.content || "").length > 0).map((a) => ({
      id: a.id || a.semantic_id, content: a.content, state: "POSSIBLY_INVALIDATED",
    })),
    confidence: reqHits.length ? confidenceFrom(reqHits.length, reqs.length) : "UNKNOWN",
  };

  // ── PM impact (tasks / effort / resources / milestones) ──────────────────
  const tasks = pm.tasks || [];
  const taskHits = affected(crText, tasks, (t) => `${t.title || ""} ${t.code || ""}`);
  // Cross-reference: a PM task that carries a matched requirement code is
  // affected even when its own wording doesn't overlap the CR text.
  for (const t of tasks) {
    if (taskHits.some((h) => h.item.id === t.id)) continue;
    const codes = [...matchedReqCodes].filter((c) => (t.title || "").includes(c));
    if (codes.length) {
      taskHits.push({
        item: t,
        matched_terms: codes,
        relationship_type: "INFERRED",
        requires_human_review: true,
        confidence: "MEDIUM",
        via_requirement_code: true,
      });
    }
  }
  // Functions become MODIFIED when one of their linked tasks is affected.
  const affectedFunctionIds = new Set(taskHits.map((h) => h.item.linked_function_id).filter(Boolean));
  if (affectedFunctionIds.size) {
    for (const f of functions) {
      if (affectedFunctionIds.has(f.id) && !function_impact.modified.some((m) => m.function_id === f.id)) {
        function_impact.modified.push({
          function: f.name || f.code || f.id,
          function_id: f.id,
          matched_terms: [],
          relationship_type: "INFERRED",
          requires_human_review: true,
          confidence: "MEDIUM",
          basis: "PM_RECORDED",
          via_task_linkage: true,
        });
        function_impact.unchanged = function_impact.unchanged.filter((n) => n !== (f.name || f.code || f.id));
      }
    }
  }
  const pm_impact = {
    affected_tasks: taskHits.map((h) => ({
      task_id: h.item.id,
      title: h.item.title,
      change_type: "MODIFIED",
      matched_terms: h.matched_terms,
      via_requirement_code: Boolean(h.via_requirement_code),
      relationship_type: "INFERRED",
      requires_human_review: true,
      confidence: h.confidence,
      basis: "PM_RECORDED",
    })),
    new_tasks: [],
    removed_tasks: [],
    resource_demand: (pm.resources || []).length
      ? { pool_size: pm.resources.length, basis: "PM_RECORDED" }
      : { pool_size: null, basis: "UNKNOWN", note: "No resource pool recorded in PM Again." },
    milestones: (pm.pmStatus || {}).milestones || [],
    basis: "PM_RECORDED",
  };

  // ── Effort impact ────────────────────────────────────────────────────────
  const recordedEffort = pm.effortSummary || null;
  const affectedCount = taskHits.length;
  let effort_impact;
  if (recordedEffort && typeof recordedEffort === "object" && Object.keys(recordedEffort).length) {
    effort_impact = {
      source: "PM_RECORDED",
      recorded: recordedEffort,
      basis: "PM_RECORDED",
      confidence: "HIGH",
      note: "Uses the recorded PM Again effort summary; no AI estimate substituted.",
    };
  } else {
    const estDays = affectedCount * 2.5 + 1;
    effort_impact = {
      source: "AI_ESTIMATE",
      total_person_days: Number(estDays.toFixed(1)),
      unit: "person-days",
      basis: "AI_ESTIMATE",
      confidence: "LOW",
      note: `No recorded effort exists; heuristic of ~2.5 person-days per affected task (${affectedCount} affected) + 1 day coordination. Human override required.`,
      formula: `${affectedCount} affected tasks × 2.5 pd + 1 pd`,
    };
  }

  // ── Timeline impact ──────────────────────────────────────────────────────
  const hasDates = tasks.some((t) => t.due_date);
  let timeline_impact;
  if (affectedCount === 0) {
    timeline_impact = { status: "NO_CHANGE", confidence: "HIGH", basis: "CALCULATED", reason: "No PM tasks matched the CR." };
  } else if (hasDates) {
    timeline_impact = {
      status: "DATE_SHIFT",
      basis: "CALCULATED",
      confidence: "MEDIUM",
      reason: `${affectedCount} PM task(s) matched; their due dates may shift.`,
      affected_task_due_dates: tasks.filter((t) => t.due_date && taskHits.some((h) => h.item.id === t.id)).map((t) => ({ id: t.id, title: t.title, due_date: t.due_date })),
    };
  } else {
    const est = effort_impact.total_person_days || 0;
    timeline_impact = {
      status: `+${Math.max(1, Math.round(est))} working days`,
      basis: "CALCULATED",
      confidence: "LOW",
      reason: `Estimated from effort impact (${est} person-days) — no recorded milestone dates in PM Again.`,
    };
  }

  // ── QA impact ────────────────────────────────────────────────────────────
  const cases = qa.cases || [];
  const cycles = qa.cycles || [];
  const defects = qa.defects || [];
  const caseHits = affected(crText, cases, (c) => `${c.checkpoint_code || ""} ${c.title || ""}`);
  const cycleHits = affected(crText, cycles, (c) => `${c.cycle_code || ""} ${c.name || ""}`);
  const defectHits = affected(crText, defects, (d) => `${d.defect_key || ""} ${d.title || ""} ${d.description_md || ""}`);
  const qa_impact = {
    revise: caseHits.map((h) => ({ checkpoint_code: h.item.checkpoint_code, title: h.item.title, confidence: h.confidence, relationship_type: "INFERRED", requires_human_review: true, basis: "QA_RECORDED" })),
    new: [],
    regression: cycleHits.map((h) => ({ cycle: h.item.name || h.item.cycle_code, confidence: h.confidence, relationship_type: "INFERRED", requires_human_review: true, basis: "QA_RECORDED" })),
    relevant_defects: defectHits.map((h) => ({ defect: h.item.defect_key || h.item.id, title: h.item.title, basis: "QA_RECORDED" })),
    signoff: { note: "Sign-off state is held by QA Again; re-sign-off required only if a cycle is re-run.", basis: "QA_RECORDED" },
    confidence: caseHits.length || cycleHits.length ? "MEDIUM" : "UNKNOWN",
  };

  // ── Infra impact ─────────────────────────────────────────────────────────
  const designs = infra.designs || [];
  const environments = infra.environments || [];
  const designHits = affected(crText, designs, (d) => `${d.name || d.designId || ""} ${d.status || ""}`);
  const envHits = affected(crText, environments, (e) => `${e.name || ""} ${e.classification || ""} ${e.provider || ""}`);

  // Bound design graph (R14): when the project has a linked Infra design,
  // project the CR text onto its recorded flow.nodes (components) and
  // flow.edges (connections) instead of guessing across all 164 designs.
  const bound = infra.boundDesign || null;
  const boundNodes = Array.isArray(bound?.flow?.nodes) ? bound.flow.nodes : [];
  const boundEdges = Array.isArray(bound?.flow?.edges) ? bound.flow.edges : [];
  const nodeHits = affected(
    crText,
    boundNodes,
    (n) => `${n.nodeId || n.id || ""} ${n.nativeService || n.service || ""} ${n.category || ""} ${n.provider || ""} ${n.label || ""}`,
  );
  const edgeHits = affected(
    crText,
    boundEdges,
    (e) => `${e.source || e.from || ""} ${e.target || e.to || ""} ${e.relation || e.type || e.label || ""}`,
  );
  const infra_questions = [];
  if (bound) {
    infra_questions.push(
      boundEdges.length === 0
        ? `Bound design ${bound.designId || bound.id} records ${boundNodes.length} component(s) but NO connections — path/carrier diversity is undefined in recorded truth.`
        : null,
      nodeHits.length === 0
        ? `Which of the ${boundNodes.length} recorded component(s) does this change touch? (no component matched the CR text)`
        : null,
      "Does the redundant path require a separate carrier / physical route? (not recorded in Infra Again)",
    );
  } else {
    infra_questions.push("No Infra design is linked to this project — assessment is against global engineering state only.");
  }
  const infra_impact = {
    bound_design: bound
      ? { design_id: bound.designId || bound.id, name: bound.name, status: bound.status, components: boundNodes.length, connections: boundEdges.length }
      : null,
    affected_designs: designHits.map((h) => ({ design_id: h.item.designId || h.item.id, status: h.item.status, confidence: h.confidence, relationship_type: "INFERRED", requires_human_review: true, basis: "INFRA_RECORDED" })),
    affected_environments: envHits.map((h) => ({ environment_id: h.item.environmentId || h.item.id, name: h.item.name, confidence: h.confidence, basis: "INFRA_RECORDED" })),
    components: boundNodes.map((n) => {
      const hit = nodeHits.find((h) => h.item === n);
      return {
        node_id: n.nodeId || n.id,
        service: n.nativeService || n.label || n.nodeId || n.id || null,
        category: n.category || null,
        provider: n.provider || null,
        change_type: hit ? "MODIFIED" : "UNCHANGED",
        matched_terms: hit ? hit.matched_terms : [],
        relationship_type: hit ? "INFERRED" : "RECORDED_UNCHANGED",
        requires_human_review: Boolean(hit),
        confidence: hit ? hit.confidence : "HIGH",
        basis: "INFRA_RECORDED",
      };
    }),
    connections: {
      recorded: boundEdges.length,
      affected: edgeHits.map((h) => ({
        source: h.item.source || h.item.from,
        target: h.item.target || h.item.to,
        type: h.item.relation || h.item.type || "UNSPECIFIED",
        matched_terms: h.matched_terms,
        relationship_type: "INFERRED",
        requires_human_review: true,
        confidence: h.confidence,
        basis: "INFRA_RECORDED",
      })),
      note: boundEdges.length === 0 ? "Bound design records no connections — connectivity impact is UNKNOWN." : null,
    },
    status: bound ? (nodeHits.length || edgeHits.length ? "PARTIAL" : "PARTIAL") : "PARTIAL",
    note: bound
      ? `Bound design ${bound.designId || bound.id} (${boundNodes.length} components, ${boundEdges.length} connections) read live from Infra Again.`
      : "Infra Again has no project binding — assessment is against global engineering state only.",
    questions: infra_questions.filter(Boolean),
  };

  // ── Commercial impact ────────────────────────────────────────────────────
  const commercial_impact = {
    status: "ESTIMATION_REQUIRED",
    currency: "THB",
    effort_person_days: effort_impact.total_person_days ?? null,
    effort_basis: effort_impact.basis,
    lines: [],
    value_status: "COMMERCIAL_VALUE = UNKNOWN",
    note: "No project rate card exists in any bounded service; currency amounts remain UNKNOWN. Effort impact is still reported.",
    confidence: "UNKNOWN",
  };

  // ── Open questions (deterministic, derived from gaps) ────────────────────
  const questions = [];
  if (function_impact.modified.length === 0) questions.push("Which project functions/workstreams does this change actually touch? (no PM function matched the CR text)");
  if (requirement_impact.revised.length === 0) questions.push("Which approved requirements must change? (no requirement matched the CR text)");
  if (pm_impact.affected_tasks.length === 0) questions.push("Which PM tasks are affected or need creation? (no task matched the CR text)");
  if (qa_impact.revise.length === 0 && qa_impact.regression.length === 0) questions.push("Which QA cases/cycles require revision or regression? (no QA item matched the CR text)");
  if (infra_impact.components.length > 0 && infra_impact.components.every((c) => c.change_type === "UNCHANGED")) {
    questions.push("Which infrastructure components are affected? (no bound-design component matched the CR text)");
  } else if (infra_impact.components.length === 0 && infra_impact.affected_designs.length === 0) {
    questions.push("Which infrastructure components are affected? (no Infra design matched the CR text)");
  }
  for (const q of infra_impact.questions || []) if (!questions.includes(q)) questions.push(q);
  questions.push("What commercial value/rate card applies? (none recorded — COMMERCIAL_VALUE UNKNOWN)");
  questions.push("Should the redundant path use a separate carrier and physical route? (path/carrier diversity is undefined in current truth)");

  // ── Summary + confidence ─────────────────────────────────────────────────
  const summary = {
    function: { affected: function_impact.modified.length, new_candidates: function_impact.new_candidate_terms.length },
    requirements: { revised_proposed: requirement_impact.revised.length, new_clarifications: 0 },
    pm: { tasks_affected: pm_impact.affected_tasks.length, new_tasks: pm_impact.new_tasks.length, effort: effort_impact.total_person_days != null ? `${effort_impact.total_person_days} pd` : "recorded" },
    timeline: timeline_impact.status,
    qa: { cases_revise: qa_impact.revise.length, new_cases: qa_impact.new.length, regression_cycles: qa_impact.regression.length },
    infra: { designs_affected: infra_impact.affected_designs.length, environments_affected: infra_impact.affected_environments.length, components_total: infra_impact.components.length, components_affected: infra_impact.components.filter((c) => c.change_type === "MODIFIED").length, connections_total: infra_impact.connections.recorded, connections_affected: infra_impact.connections.affected.length, bound_design: infra_impact.bound_design?.design_id || null },
    commercial: commercial_impact.value_status,
    open_questions: questions.length,
  };

  return {
    engine: "OIDA-R13-deterministic",
    generated_at: new Date().toISOString(),
    cr: { code: cr?.code, requested_change: cr?.requested_change, status: cr?.status },
    function_impact,
    requirement_impact,
    pm_impact,
    effort_impact,
    timeline_impact,
    qa_impact,
    infra_impact,
    commercial_impact,
    open_questions: questions,
    summary,
    stale_policy: "Re-computed live from bounded authorities each time; never persisted in OIDA.",
  };
}
