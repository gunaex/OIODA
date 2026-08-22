// Typed API surface over the bounded services. `da` = Document Again (design
// authority), `pm` = PM Again (execution), `qa` = QA Again (verification),
// `account` = Account Again (identity), `conductor` = orchestration status.
import { get, post, request, put, patch, del } from "./client";
import { getActor } from "../auth/AuthContext";

function daHeaders() {
  return { "X-Actor": getActor() };
}

// ───────────────────────── Document Again ─────────────────────────
export const documentApi = {
  listProjects: (state) => get("da", `/projects${state ? `?state=${encodeURIComponent(state)}` : ""}`, { headers: daHeaders() }),
  getProject: (id) => get("da", `/projects/${id}`, { headers: daHeaders() }),
  // R16 project lifecycle (Document Again is the lifecycle authority)
  archiveProject: (id) => post("da", `/projects/${id}/archive`, {}, { headers: daHeaders() }),
  restoreProject: (id) => post("da", `/projects/${id}/restore`, {}, { headers: daHeaders() }),
  cloneProject: (id, body) => post("da", `/projects/${id}/clone`, body, { headers: daHeaders() }),
  deleteImpact: (id) => get("da", `/projects/${id}/delete-impact`, { headers: daHeaders() }),
  deleteProject: (id, confirmKey) => post("da", `/projects/${id}/delete`, { confirm_key: confirmKey }, { headers: daHeaders() }),
  projectHome: (id) => get("da", `/projects/${id}/home`, { headers: daHeaders() }),
  listRequirements: (id) => get("da", `/projects/${id}/requirements`, { headers: daHeaders() }),
  getRequirement: (id) => get("da", `/requirements/${id}`, { headers: daHeaders() }),
  createRequirement: (body) => post("da", "/requirements", body, { headers: daHeaders() }),
  listArtifacts: (id) => get("da", `/projects/${id}/artifacts`, { headers: daHeaders() }),
  getArtifact: (id) => get("da", `/artifacts/${id}`, { headers: daHeaders() }),
  getRevision: (id) => get("da", `/revisions/${id}`, { headers: daHeaders() }),
  getRevisionDocument: (id) => get("da", `/revisions/${id}/document`, { headers: daHeaders() }),
  listBaselines: (id) => get("da", `/projects/${id}/baselines`, { headers: daHeaders() }),
  getBaseline: (id) => get("da", `/baselines/${id}`, { headers: daHeaders() }),
  projectMemory: (id) => get("da", `/projects/${id}/project-memory`, { headers: daHeaders() }),
  listTraces: (id) => get("da", `/projects/${id}/traces`, { headers: daHeaders() }),
  traceGraph: (id) => get("da", `/projects/${id}/trace-graph`, { headers: daHeaders() }),
  semanticContext: (id, semanticId) =>
    get("da", `/projects/${id}/semantic-context/${semanticId}`, { headers: daHeaders() }),
  listFlows: (id) => get("da", `/projects/${id}/flows`, { headers: daHeaders() }),
  listArchitecture: (id) => get("da", `/projects/${id}/architecture`, { headers: daHeaders() }),
  listChangeRequests: (id) => get("da", `/projects/${id}/change-requests`, { headers: daHeaders() }),
  getChangeRequest: (id) => get("da", `/change-requests/${id}`, { headers: daHeaders() }),
  listChangeSets: (id) => get("da", `/projects/${id}/change-sets`, { headers: daHeaders() }),
  timeline: (id) => get("da", `/projects/${id}/timeline`, { headers: daHeaders() }),
  auditEvents: (params = {}) =>
    get("da", `/audit-events?${new URLSearchParams(params)}`, { headers: daHeaders() }),
  ecosystemTrace: (id) => get("da", `/projects/${id}/ecosystem-trace`, { headers: daHeaders() }),
  executionHandoffs: (id) => get("da", `/projects/${id}/handoffs/execution`, { headers: daHeaders() }),
  qaHandoffs: (id) => get("da", `/projects/${id}/handoffs/qa`, { headers: daHeaders() }),
  ecosystemEvents: (id) => get("da", `/projects/${id}/ecosystem-events`, { headers: daHeaders() }),
  search: (id, q) => get("da", `/projects/${id}/search?q=${encodeURIComponent(q)}`, { headers: daHeaders() }),
  exportRevision: (revId, format = "xlsx") =>
    `/api/da/revisions/${revId}/export?format=${format}`,
  baselinePackage: (baselineId) => `/api/da/baselines/${baselineId}/package-v4`,
  // R10 requirement change lifecycle
  requirementRevisions: (id) => get("da", `/requirements/${id}/revisions`, { headers: daHeaders() }),
  createRequirementDraft: (id) =>
    post("da", `/requirements/${id}/draft`, {}, { headers: daHeaders() }),
  updateRequirementDraft: (id, revId, body) =>
    put("da", `/requirements/${id}/draft/${revId}`, body, { headers: daHeaders() }),
  listChanges: (id) => get("da", `/projects/${id}/changes`, { headers: daHeaders() }),
  getChange: (id) => get("da", `/changes/${id}`, { headers: daHeaders() }),
  changeImpact: (id) => get("da", `/changes/${id}/impact`, { headers: daHeaders() }),
  regenerateChange: (id, mode) =>
    post("da", `/changes/${id}/regenerate`, { mode }, { headers: daHeaders() }),
  confirmChange: (id, token) =>
    post("da", `/changes/${id}/confirm`, { confirmation_token: token }, { headers: daHeaders() }),
  // R10 CR (commercial change control)
  createChangeRequest: (body) => post("da", "/change-requests", body, { headers: daHeaders() }),
  getChangeRequest: (id) => get("da", `/change-requests/${id}`, { headers: daHeaders() }),
  crImpact: (id) => get("da", `/change-requests/${id}/impact`, { headers: daHeaders() }),
  saveCrImpact: (id, body) => put("da", `/change-requests/${id}/impact`, body, { headers: daHeaders() }),
  crCustomerApproval: (id, body) =>
    post("da", `/change-requests/${id}/customer-approval`, body, { headers: daHeaders() }),
  // R10.1 CR creation + impact trust
  suggestCrClassification: (projectId, affectedSemanticIds) =>
    post("da", "/change-requests/suggest-classification", { project_id: projectId, affected_semantic_ids: affectedSemanticIds }, { headers: daHeaders() }),
  analyzeCrImpact: (id) => post("da", `/change-requests/${id}/analyze-impact`, {}, { headers: daHeaders() }),
  getCrImpactAnalysis: (id) => get("da", `/change-requests/${id}/impact-analysis`, { headers: daHeaders() }),
  reviewCrImpactAnalysis: (id, analysisId, body) =>
    post("da", `/change-requests/${id}/impact-analysis/review`, { analysis_id: analysisId, ...body }, { headers: daHeaders() }),
  // R13 CR lifecycle (human-driven transition)
  transitionCr: (id, toStatus, note) =>
    post("da", `/change-requests/${id}/transition`, { to_status: toStatus, note }, { headers: daHeaders() }),
  // R11 new project + OIDA suggestions
  createProject: (body) => post("da", "/projects", body, { headers: daHeaders() }),
  getWorkspaceBindings: (id) => get("da", `/projects/${id}/workspace-bindings`, { headers: daHeaders() }),
  updateWorkspaceBindings: (id, body) => put("da", `/projects/${id}/workspace-bindings`, body, { headers: daHeaders() }),
  projectTruth: (id) => get("da", `/projects/${id}/truth`, { headers: daHeaders() }),
  commandCenter: (id) => get("da", `/projects/${id}/command-center`, { headers: daHeaders() }),
  projectCopilot: (id, body) => post("da", `/projects/${id}/copilot`, body, { headers: daHeaders() }),
  projectBriefing: (id) => get("da", `/projects/${id}/briefing`, { headers: daHeaders() }),
  markBriefingReviewed: (id, body) => post("da", `/projects/${id}/briefing/mark-reviewed`, body, { headers: daHeaders() }),
  briefingAi: (id) => post("da", `/projects/${id}/briefing/ai`, {}, { headers: daHeaders() }),
  portfolio: () => get("da", "/portfolio/command-center", { headers: daHeaders() }),
  markPortfolioReviewed: (body) => post("da", "/portfolio/mark-reviewed", body, { headers: daHeaders() }),
  portfolioCopilot: (body) => post("da", "/portfolio/copilot", body, { headers: daHeaders() }),
  generateSuggestions: (id, mode = "STANDARD") =>
    post("da", `/projects/${id}/suggestions/generate`, { mode }, { headers: daHeaders() }),
  listSuggestions: (id) => get("da", `/projects/${id}/suggestions`, { headers: daHeaders() }),
  answerSuggestion: (id, answer, source = "CUSTOMER") =>
    post("da", `/suggestions/${id}/answer`, { answer, source }, { headers: daHeaders() }),
  interpretSuggestion: (id) => post("da", `/suggestions/${id}/interpret`, {}, { headers: daHeaders() }),
  reviewSuggestion: (id, decision) =>
    post("da", `/suggestions/${id}/review`, { decision }, { headers: daHeaders() }),
  aiProviders: () => get("da", "/ai/providers", { headers: daHeaders() }),
  aiProvidersTest: (id) => post("da", `/ai/providers/${id}/test`, {}, { headers: daHeaders() }),
  aiProviderSettings: (id) => get("da", `/ai/providers/${id}/settings`, { headers: daHeaders() }),
  updateAiProviderSettings: (id, body) => put("da", `/ai/providers/${id}/settings`, body, { headers: daHeaders() }),
  aiProviderModels: (id, apiKey) =>
    get("da", `/ai/providers/${id}/models`, {
      headers: { ...daHeaders(), ...(apiKey ? { "X-Provider-API-Key": apiKey } : {}) },
    }),
  // R15 Multi-Agent Council
  aiCapabilities: () => get("da", "/ai/capabilities", { headers: daHeaders() }),
  councilMode: () => get("da", "/ai/council/mode", { headers: daHeaders() }),
  councilConsult: (projectId, body) =>
    post("da", `/projects/${projectId}/council/consult`, body, { headers: daHeaders() }),
  councilConsultations: (projectId) =>
    get("da", `/projects/${projectId}/council/consultations`, { headers: daHeaders() }),
  councilConsultation: (projectId, consultationId) =>
    get("da", `/projects/${projectId}/council/consultations/${consultationId}`, { headers: daHeaders() }),
  councilCheckStale: (consultationId, contextEnvelope) =>
    post("da", `/council/consultations/${consultationId}/check-stale`, { context_envelope: contextEnvelope }, { headers: daHeaders() }),
  councilReview: (consultationId, body) =>
    post("da", `/council/consultations/${consultationId}/review`, body, { headers: daHeaders() }),
  councilToSuggestion: (consultationId, finding) =>
    post("da", `/council/consultations/${consultationId}/to-suggestion`, { finding }, { headers: daHeaders() }),
  councilRerun: (consultationId, contextEnvelope) =>
    post("da", `/council/consultations/${consultationId}/rerun`, { context_envelope: contextEnvelope }, { headers: daHeaders() }),
};

// ───────────────────────── PM Again ─────────────────────────
export const pmApi = {
  listProjects: () => get("pm", "/projects"),
  getProject: (slug) => get("pm", `/projects/${slug}`),
  functions: (slug) => get("pm", `/${slug}/functions`),
  tasks: (slug) => get("pm", `/${slug}/tasks`),
  gantt: (slug) => get("pm", `/${slug}/gantt`),
  dashboard: (slug) => get("pm", `/${slug}/dashboard`),
  activity: (slug) => get("pm", `/${slug}/activity`),
  pmStatus: (slug) => get("pm", `/${slug}/pm-status`),
  createTask: (slug, body) => post("pm", `/${slug}/tasks`, body),
  updateTask: (slug, id, body) => request("pm", `/${slug}/tasks/${id}`, { method: "PUT", body }),
  deleteTask: (slug, id) => del("pm", `/${slug}/tasks/${id}`),
  // Board
  boardItems: (slug) => get("pm", `/${slug}/board-items`),
  createBoardItem: (slug, body) => post("pm", `/${slug}/board-items`, body),
  updateBoardItem: (slug, id, body) => put("pm", `/${slug}/board-items/${id}`, body),
  promoteBoardItem: (slug, id) => post("pm", `/${slug}/board-items/${id}/promote`, {}),
  // Notes + Notes Hub
  notes: (slug) => get("pm", `/${slug}/notes`),
  createNote: (slug, body) => post("pm", `/${slug}/notes`, body),
  notePages: (slug) => get("pm", `/${slug}/note-pages`),
  notePage: (slug, id) => get("pm", `/${slug}/note-pages/${id}`),
  createNotePage: (slug, body) => post("pm", `/${slug}/note-pages`, body),
  // Resources
  resources: () => get("pm", "/resources"),
  resourceAllocations: (slug) => get("pm", `/${slug}/resource-allocations`),
  // Effort
  effortSummary: (slug) => get("pm", `/${slug}/effort-estimates/summary`),
  effortBudget: (slug) => get("pm", `/${slug}/effort-budget`),
  effortEstimates: (slug) => get("pm", `/${slug}/effort-estimates`),
  // Reports
  pmReport: (slug, name) => get("pm", `/${slug}/reports/${name}`),
  // Documents + Whiteboards
  documents: (slug) => get("pm", `/${slug}/documents`),
  whiteboards: (slug) => get("pm", `/${slug}/whiteboards`),
};

// ───────────────────────── QA Again ─────────────────────────
export const qaApi = {
  listProjects: () => get("qa", "/projects"),
  getProject: (slug) => get("qa", `/projects/${slug}`),
  dashboard: (slug) => get("qa", `/${slug}/dashboard`),
  // Suites + revisions + cases
  suites: (slug) => get("qa", `/${slug}/suites`),
  createSuite: (slug, body) => post("qa", `/${slug}/suites`, body),
  getSuite: (slug, id) => get("qa", `/${slug}/suites/${id}`),
  revisions: (slug, suiteId) => get("qa", `/${slug}/suites/${suiteId}/revisions`),
  createRevision: (slug, suiteId, body) => post("qa", `/${slug}/suites/${suiteId}/revisions`, body),
  publishRevision: (slug, suiteId, revId) => post("qa", `/${slug}/suites/${suiteId}/revisions/${revId}/publish`, {}),
  cases: (slug, revisionId) => get("qa", `/${slug}/revisions/${revisionId}/cases`),
  createCase: (slug, revisionId, body) => post("qa", `/${slug}/revisions/${revisionId}/cases`, body),
  updateCase: (slug, revisionId, caseId, body) => put("qa", `/${slug}/revisions/${revisionId}/cases/${caseId}`, body),
  // Cycles + results
  cycles: (slug) => get("qa", `/${slug}/cycles`),
  createCycle: (slug, body) => post("qa", `/${slug}/cycles`, body),
  cycleResults: (slug, cycleId) => get("qa", `/${slug}/cycles/${cycleId}/results`),
  updateResult: (slug, cycleId, resultId, body) => put("qa", `/${slug}/cycles/${cycleId}/results/${resultId}`, body),
  reviewResult: (slug, cycleId, resultId, body) => post("qa", `/${slug}/cycles/${cycleId}/results/${resultId}/review`, body),
  // Defects + sign-offs
  defects: (slug) => get("qa", `/${slug}/defects`),
  createDefect: (slug, body) => post("qa", `/${slug}/defects`, body),
  updateDefect: (slug, id, body) => put("qa", `/${slug}/defects/${id}`, body),
  signoffs: (slug, cycleId) => get("qa", `/${slug}/cycles/${cycleId}/signoffs`),
  createSignoff: (slug, cycleId, body) => post("qa", `/${slug}/cycles/${cycleId}/signoffs`, body),
  // Reports + exports
  reports: (slug, name) => get("qa", `/${slug}/reports/${name}`),
  exportExcel: (slug, cycleId) => `/api/qa/${slug}/cycles/${cycleId}/export/excel`,
  exportZip: (slug, cycleId) => `/api/qa/${slug}/cycles/${cycleId}/export/zip`,
};

// ───────────────────────── Account Again ─────────────────────────
export const accountApi = {
  tenants: () => get("account", "/tenants"),
  accounts: () => get("account", "/accounts"),
  roles: () => get("account", "/roles"),
  permissions: () => get("account", "/permissions"),
  productEntitlements: () => get("account", "/product-entitlements"),
  audit: () => get("account", "/audit"),
  reauth: (email, password) => post("account", "/auth/reauth", { email, password }),
  // R-identity: single sign-on — one human credential → signed ecosystem identity token
  ecosystemToken: (email, password) => post("account", "/auth/ecosystem-token", { email, password }),
  changePassword: (currentPassword, newPassword) =>
    post("account", "/auth/change-password", { currentPassword, newPassword }),
};

// ───────────────────────── Conductor (read-only status) ─────────────────────────
export const conductorApi = {
  services: () => get("conductor", "/integration/services"),
};

// ───────────────────────── Infra Again (read-only project surface) ─────────────────────────
// Infra Again has NO project/tenant/baseline linkage today; these endpoints read
// its global engineering state. OIDA shows them honestly (read-only, unlinked).
export const infraApi = {
  health: () => get("infra", "/health"),
  environments: () => get("infra", "/environments"),
  capabilities: () => get("infra", "/capabilities"),
  designs: () => get("infra", "/designs"),
  getDesign: (id) => get("infra", `/designs/${id}`),
  designFeasibility: (id) => get("infra", `/designs/${id}/feasibility`),
  workspaces: () => get("infra", "/workspaces"),
  implementationPlan: (id) => get("infra", `/implementation-plans/${id}`),
  executionRuns: () => get("infra", "/execution-runs"),
  getExecutionRun: (id) => get("infra", `/execution-runs/${id}`),
  promotions: () => get("infra", "/promotions"),
  uat: () => get("infra", "/uat"),
  productionReadiness: () => get("infra", "/production-readiness"),
};

// ───────────────────────── R17 Deliverable Standard Framework ─────────────────────────
export const deliverableApi = {
  taxonomy: () => get("da", "/deliverable-taxonomy"),
  standards: (domain) => get("da", `/deliverable-standards${domain ? `?domain=${domain}` : ""}`),
  layouts: () => get("da", "/deliverable-layouts"),
  profile: (projectId) => get("da", `/projects/${projectId}/deliverable-profile`),
  putProfile: (projectId, body) => put("da", `/projects/${projectId}/deliverable-profile`, body),
  matrix: (projectId) => get("da", `/projects/${projectId}/deliverable-matrix`),
  generateMatrix: (projectId) => post("da", `/projects/${projectId}/deliverable-matrix/generate`, {}),
  gaps: (projectId) => get("da", `/projects/${projectId}/deliverable-gaps`),
  instance: (projectId, code) => get("da", `/projects/${projectId}/deliverables/${code}`),
  transition: (projectId, code, body) =>
    post("da", `/projects/${projectId}/deliverables/${code}/transition`, body),
  overrideApplicability: (projectId, code, applicability) =>
    post("da", `/projects/${projectId}/deliverables/${code}/applicability`, { applicability }),
  exportWorkbookUrl: (projectId, mode) => `/api/da/projects/${projectId}/exports/${mode}`,
};

// ───────────────────────── R17.1 Human Deliverables ─────────────────────────
export const humanApi = {
  catalog: () => get("da", "/human-deliverable-catalog"),
  list: (projectId) => get("da", `/projects/${projectId}/human-deliverables`),
  detail: (projectId, code) => get("da", `/projects/${projectId}/human-deliverables/${code}`),
  precheck: (projectId, code) => post("da", `/projects/${projectId}/human-deliverables/${code}/precheck`, {}),
  generate: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/generate`, body || {}),
  transition: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/transition`, body),
  signoff: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/signoff`, body),
  versions: (projectId, code) => get("da", `/projects/${projectId}/human-deliverables/${code}/versions`),
  refreshFreshness: (projectId, code) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/refresh`, {}),
  signoffRegister: (projectId) => get("da", `/projects/${projectId}/signoff-register`),
  signoffGates: (projectId) => get("da", `/projects/${projectId}/signoff-gates`),
  governanceFlags: (projectId) => get("da", `/projects/${projectId}/governance-flags`),
  governancePolicy: (projectId) => get("da", `/projects/${projectId}/governance-policy`),
  putGovernancePolicy: (projectId, body) => put("da", `/projects/${projectId}/governance-policy`, body),
  resolveGate: (projectId, gateId, body) =>
    post("da", `/projects/${projectId}/gates/${gateId}/resolve`, body),
  brief: (projectId, code, role) =>
    get("da", `/projects/${projectId}/human-deliverables/${code}/brief${role ? `?role=${encodeURIComponent(role)}` : ""}`),
  reviewerEvidence: (projectId, code, role, purpose = "REVIEW") => {
    const params = new URLSearchParams({ purpose });
    if (role) params.set("role", role);
    return get("da", `/projects/${projectId}/human-deliverables/${code}/reviewer-evidence?${params}`);
  },
  impact: (projectId, code) =>
    get("da", `/projects/${projectId}/human-deliverables/${code}/impact`),
  impactConfirmations: (projectId, code) =>
    get("da", `/projects/${projectId}/human-deliverables/${code}/impact-confirmations`),
  reviewImpact: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/impact-confirmations`, body),
  previewImpactAction: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/impact-actions/preview`, body),
  executeImpactAction: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/impact-actions/execute`, body),
  impactActionHistory: (projectId) => get("da", `/projects/${projectId}/impact-actions`),
  impactActionRegistry: () => get("da", "/impact-actions/registry"),
  impactResolutionHistory: (projectId) => get("da", `/projects/${projectId}/impact-resolutions`),
  recheckImpactResolution: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/impact-resolutions/recheck`, body),
  aiReviewer: (projectId, code, body) =>
    post("da", `/projects/${projectId}/human-deliverables/${code}/ai-reviewer`, body || {}),
  aiStatus: () => get("da", "/reviewer-ai/status"),
  acceptChangeRequest: (projectId, crCode, body) =>
    post("da", `/projects/${projectId}/change-requests/${crCode}/accept`, body),
  mySignoffs: (projectId) => get("da", `/projects/${projectId}/my-signoffs`),
  auditTrail: (projectId) => get("da", `/projects/${projectId}/deliverable-audit-trail`),
  exportUrl: (projectId, kind, code) => {
    if (kind === "human") return `/api/da/projects/${projectId}/exports/human/${code}`;
    if (kind === "snapshot") return `/api/da/projects/${projectId}/exports/snapshot/${code}`;
    if (kind === "signoff-evidence") return `/api/da/projects/${projectId}/signoff-evidence`;
    if (kind === "acceptance-package") return `/api/da/projects/${projectId}/acceptance-package`;
    if (kind === "governance-flag-register") return `/api/da/projects/${projectId}/governance-flag-register`;
    if (kind === "risk-overrides") return `/api/da/projects/${projectId}/risk-overrides`;
    return null;
  },
};
