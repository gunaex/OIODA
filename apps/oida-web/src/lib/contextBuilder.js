// OIDA Context Builder — builds a bounded, authority-annotated Context Envelope
// for AI consultation. OIDA-owned orchestration metadata ONLY: it projects facts
// from the bounded services and records where each fact came from. No truth is
// copied into OIDA persistence.

const INTENT_RULES = [
  {
    id: "cr_impact",
    test: /change request|cr-\d|change impact|impact of this change|requested change/i,
    label: "Change Request / impact analysis",
  },
  {
    id: "impact",
    test: /impact|change|bandwidth|gbps|mbps|direct connect|connectiv|affect/i,
    label: "Change / impact analysis",
  },
  {
    id: "qa",
    test: /qa|uat|fail|defect|test|validation|sign.?off|evidence/i,
    label: "QA / validation review",
  },
  {
    id: "pm",
    test: /task|progress|schedule|resource|effort|plan|milestone|owner/i,
    label: "PM / execution review",
  },
  {
    id: "general",
    test: /.*/,
    label: "General consultation",
  },
];

// Domain detection is independent of the single display label above: a
// cross-domain question (e.g. "PM tasks related to HIGH severity QA defects")
// must pull PM and QA context together, not force one of them out.
const DOMAIN_RULES = [
  { id: "pm", test: /task|progress|schedule|resource|effort|plan|milestone|owner|workstream|gantt|whiteboard|board|timeline/i },
  { id: "qa", test: /qa|uat|fail|defect|test|validation|sign.?off|evidence|coverage|case|cycle|checkpoint|severity/i },
  { id: "infra", test: /infra|bandwidth|direct connect|landing zone|network|connectiv|component|vpc|subnet|aws|compute|storage|gbps|mbps/i },
];

function detectDomains(question) {
  const q = question || "";
  const domains = new Set(["document"]);
  for (const r of DOMAIN_RULES) {
    if (r.test.test(q)) domains.add(r.id);
  }
  // A question with no service keyword is a general consultation → all domains.
  if (domains.size === 1) {
    domains.add("pm");
    domains.add("qa");
    domains.add("infra");
  }
  return [...domains];
}

export function detectIntent(question) {
  const rule = INTENT_RULES.find((r) => r.test.test(question || "")) || INTENT_RULES[INTENT_RULES.length - 1];
  return { id: rule.id, label: rule.label, domains: detectDomains(question) };
}

function relevant(question, text) {
  if (!question) return true;
  const words = question.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 2);
  if (words.length === 0) return true;
  return words.some((w) => (text || "").toLowerCase().includes(w));
}

// Fact class + approval-state discipline (Phase 8). An inferred relationship
// is NEVER authoritative truth — it is a labeled proposal requiring human review.
const FACT_CLASS = {
  requirement: "FACT",
  task: "FACT",
  defect: "FACT",
  clarification: "CLARIFICATION",
  assumption: "ASSUMPTION",
  decision: "DECISION",
  proposal: "PROPOSAL",
  inferred_relationship: "INFERRED_RELATIONSHIP",
};

function approvalState(kind, record) {
  if (kind === "decision") return "HUMAN_APPROVED";
  if (kind === "assumption") return record.resolved ? "HUMAN_APPROVED" : "PROPOSED";
  if (kind === "clarification") return record.resolved ? "RESOLVED" : "OPEN";
  if (kind === "requirement") return record.status === "ACCEPTED" ? "HUMAN_APPROVED" : "PROPOSED";
  if (kind === "task") return record.status === "Done" ? "COMPLETE" : "IN_PROGRESS";
  if (kind === "defect") return record.status === "CLOSED" ? "CLOSED" : "OPEN";
  return "OBSERVED";
}

// Cross-service inference is keyword-overlap only and is ALWAYS labeled.
function inferRelationships(pmTasks, qaDefects, question) {
  const out = [];
  const q = (question || "").toLowerCase();
  for (const t of pmTasks) {
    for (const d of qaDefects) {
      const titleT = (t.title || "").toLowerCase();
      const titleD = (d.title || "").toLowerCase();
      const shared = titleT.split(/[^a-z0-9]+/).filter((w) => w.length > 3 && titleD.includes(w));
      if (shared.length === 0) continue;
      out.push({
        relationship: `${t.title} may relate to defect ${d.defect_key || d.id}`,
        relationship_type: "INFERRED",
        confidence: "MEDIUM",
        source_evidence: { shared_terms: shared, question },
        requires_human_review: true,
      });
    }
  }
  return out;
}

export function buildContextEnvelope({ project, question, requirements = [], clarifications = [], assumptions = [], decisions = [], pmTasks = [], pmEffort = null, pmResources = [], qaDefects = [], qaSuites = [], qaCases = [], qaCycles = [], qaExecutions = [], infra = null, traceEdges = [] }) {
  const intent = detectIntent(question);
  const now = new Date().toISOString();
  const targetsRequirements = /requirement|coverage|traceability|scope/i.test(question || "");

  // Intent-driven selection (data minimization). A coverage/impact question
  // makes requirements the subject, so ALL of them are relevant; otherwise
  // only keyword-relevant ones.
  const reqs = requirements
    .map((r) => ({ ...r, _rel: targetsRequirements || relevant(question, `${r.title} ${r.code} ${r.source_reference || ""}`) }))
    .filter((r) => intent.domains.includes("document") && (intent.id === "general" || r._rel));
  const reqCodes = new Set(reqs.map((r) => r.code));
  const traces = traceEdges.filter((e) => reqCodes.has(e.source) || reqCodes.has(e.target));

  const included = [];
  const excluded = [];
  const push = (list, fact) => (fact._rel ? included : excluded).push(fact);

  reqs.forEach((r) => push(r._rel ? included : excluded, {
    fact_type: "requirement", fact_class: FACT_CLASS.requirement, id: r.code, content: r.title,
    authority: "DOCUMENT_AGAIN", source_object_id: r.id, approval_state: approvalState("requirement", r), retrieved_at: now, _rel: r._rel,
  }));
  clarifications.forEach((c) => push(relevant(question, `${c.question} ${c.answer}`), {
    fact_type: "clarification", fact_class: FACT_CLASS.clarification, id: c.id || c.semantic_id, content: c.question, answer: c.answer,
    authority: "DOCUMENT_AGAIN", approval_state: approvalState("clarification", c), retrieved_at: now,
    _rel: relevant(question, `${c.question} ${c.answer}`),
  }));
  assumptions.forEach((a) => push(relevant(question, a.content), {
    fact_type: "assumption", fact_class: FACT_CLASS.assumption, id: a.id || a.semantic_id, content: a.content,
    authority: "DOCUMENT_AGAIN", approval_state: approvalState("assumption", a), retrieved_at: now,
    _rel: relevant(question, a.content),
  }));
  decisions.forEach((d) => push(relevant(question, `${d.title} ${d.content}`), {
    fact_type: "decision", fact_class: FACT_CLASS.decision, id: d.id || d.semantic_id, content: d.title || d.content,
    authority: "DOCUMENT_AGAIN", approval_state: "HUMAN_APPROVED", retrieved_at: now,
    _rel: relevant(question, `${d.title} ${d.content}`),
  }));

  const pmTasksSel = intent.domains.includes("pm")
    ? pmTasks.map((t) => ({ ...t, _rel: /task|plan|milestone|resource|effort|owner|workstream|schedule/i.test(question || "") || relevant(question, `${t.title} ${t.code || ""}`) })).filter((t) => intent.id === "general" || t._rel)
    : [];
  pmTasksSel.forEach((t) => push(true, {
    fact_type: "task", fact_class: FACT_CLASS.task, id: t.code || t.id, title: t.title, status: t.status,
    authority: "PM_AGAIN", source_object_id: t.id, approval_state: approvalState("task", t), retrieved_at: now, _rel: true,
  }));
  const qaDefectsSel = intent.domains.includes("qa")
    ? qaDefects.map((d) => ({ ...d, _rel: /defect|fail|bug|high|severity|blocked/i.test(question || "") || relevant(question, `${d.title} ${d.description_md || ""}`) })).filter((d) => intent.id === "general" || d._rel)
    : [];
  qaDefectsSel.forEach((d) => push(true, {
    fact_type: "defect", fact_class: FACT_CLASS.defect, id: d.defect_key || d.id, title: d.title, severity: d.severity,
    authority: "QA_AGAIN", source_object_id: d.id, approval_state: approvalState("defect", d), retrieved_at: now, _rel: true,
  }));

  // Executions only when the intent is QA/impact (data minimization).
  const executionsSel = intent.domains.includes("qa")
    ? qaExecutions.filter((e) => intent.id === "general" || relevant(question, `${e.checkpoint_code || ""} ${e.status || ""}`))
    : [];

  // QA coverage-source facts (bounded) — included so QA_AGAIN is visible as
  // the authority for what *does* exist, even when no defect matches.
  if (intent.domains.includes("qa")) {
    (qaSuites || []).slice(0, 10).forEach((s) => push(true, {
      fact_type: "suite", fact_class: "FACT", id: s.suite_code || s.id, title: s.name, status: s.status,
      authority: "QA_AGAIN", source_object_id: s.id, approval_state: s.status === "ACTIVE" ? "ACTIVE" : "OBSERVED", retrieved_at: now, _rel: true,
    }));
    (qaCases || []).slice(0, 50).forEach((c) => push(true, {
      fact_type: "case", fact_class: "FACT", id: c.checkpoint_code || c.id, title: c.title, status: c.status || "DRAFT",
      authority: "QA_AGAIN", source_object_id: c.id, approval_state: "PROPOSED", retrieved_at: now, _rel: true,
    }));
  }

  // INFRA context is read from Infra Again. When a design is linked to the
  // project, its flow.nodes/edges become component + connection facts;
  // otherwise the global engineering state is shown honestly.
  const boundDesign = infra?.boundDesign || null;
  const infraSel = intent.domains.includes("infra") && infra
    ? {
        note: boundDesign
          ? `Bound design ${boundDesign.designId || boundDesign.id} read live from INFRA_AGAIN (${(boundDesign.flow?.nodes || []).length} components, ${(boundDesign.flow?.edges || []).length} connections).`
          : "INFRA_AGAIN has no project binding — global engineering state, read-only.",
        bound_design: boundDesign ? { designId: boundDesign.designId || boundDesign.id, name: boundDesign.name, status: boundDesign.status } : null,
        environments: Array.isArray(infra.environments) ? infra.environments : [],
        designs: (Array.isArray(infra.designs) ? infra.designs : []).filter((d) => relevant(question, `${d.name || ""} ${d.status || ""}`)),
        execution_runs: (Array.isArray(infra.executionRuns) ? infra.executionRuns : []).filter((r) => relevant(question, `${r.name || ""} ${r.status || ""}`)),
        components: Array.isArray(boundDesign?.flow?.nodes) ? boundDesign.flow.nodes : [],
        connections: Array.isArray(boundDesign?.flow?.edges) ? boundDesign.flow.edges : [],
      }
    : null;
  if (infraSel) {
    infraSel.environments.slice(0, 10).forEach((e) => push(true, {
      fact_type: "environment", fact_class: "FACT", id: e.environmentId || e.name, title: e.name, status: e.classification,
      authority: "INFRA_AGAIN", source_object_id: e.environmentId, approval_state: "OBSERVED", retrieved_at: now, _rel: true,
    }));
    infraSel.designs.slice(0, 10).forEach((d) => push(true, {
      fact_type: "design", fact_class: "FACT", id: d.designId || d.id, title: d.name, status: d.status,
      authority: "INFRA_AGAIN", source_object_id: d.designId, approval_state: d.status === "BASELINE_FROZEN" ? "FROZEN" : "OBSERVED", retrieved_at: now, _rel: true,
    }));
    infraSel.components.slice(0, 50).forEach((n) => push(true, {
      fact_type: "component", fact_class: "FACT", id: n.nodeId || n.id, title: n.nativeService || n.label || n.nodeId || n.id || "component",
      status: n.category || null, provider: n.provider || null,
      authority: "INFRA_AGAIN", source_object_id: n.nodeId || n.id, approval_state: "OBSERVED", retrieved_at: now, _rel: true,
    }));
    infraSel.connections.slice(0, 50).forEach((e) => push(true, {
      fact_type: "connection", fact_class: "FACT", id: e.id || `${e.source || e.from}→${e.target || e.to}`, title: `${e.source || e.from} → ${e.target || e.to}`, status: e.relation || e.type || "UNSPECIFIED",
      authority: "INFRA_AGAIN", source_object_id: e.id, approval_state: "OBSERVED", retrieved_at: now, _rel: true,
    }));
  }

  const inferred = inferRelationships(pmTasksSel, qaDefectsSel, question);

  // Coverage gap: which requirements are referenced by no QA case
  // (traceability_md or title references the requirement code). Honest —
  // when QA has no mapped cases yet, every requirement is uncovered.
  const coverage = reqs.map((r) => {
    const coveredBy = (qaCases || []).filter((c) =>
      `${c.traceability_md || ""} ${c.title || ""} ${c.checkpoint_code || ""}`.includes(r.code)
    );
    return {
      requirement: r.code,
      covered: coveredBy.length > 0,
      covered_by_cases: coveredBy.map((c) => c.checkpoint_code || c.id),
    };
  });
  const uncovered = coverage.filter((c) => !c.covered).map((c) => c.requirement);

  const authority_map = included.map(({ _rel, ...fact }) => fact);
  const authority_coverage = {};
  authority_map.forEach((f) => { authority_coverage[f.authority] = (authority_coverage[f.authority] || 0) + 1; });

  return {
    context_version: "1.1",
    project: { id: project?.id, key: project?.key, name: project?.name },
    intent: intent.label,
    question,
    requirements: reqs.map(({ _rel, ...r }) => r),
    clarifications,
    assumptions,
    decisions,
    pm_context: {
      tasks: pmTasksSel.map(({ _rel, ...t }) => t),
      effort: pmEffort || null,
      resources: pmResources,
      milestones: [],
      risks: [],
    },
    qa_context: {
      suites: qaSuites.slice(0, 20),
      cases: qaCases.slice(0, 50),
      cycles: qaCycles.slice(0, 20),
      executions: executionsSel,
      defects: qaDefectsSel.map(({ _rel, ...d }) => d),
      signoffs: [],
    },
    coverage: { total_requirements: coverage.length, uncovered, details: coverage },
    infra_context: infraSel,
    traceability: traces.map((t) => ({ source: t.source, target: t.target, relation: t.relation })),
    inferred_relationships: inferred,
    authority_map,
    freshness: { built_at: now, note: "OIDA projection metadata; authorities remain the bounded services." },
    excluded: { count: excluded.length, sample: excluded.slice(0, 10).map((e) => e.fact_type + ":" + (e.id || e.title)) },
    constraints: { human_led: true, ai_is_not_authority: true },
    intent_id: intent.id,
    included_count: included.length,
    authority_coverage,
  };
}
