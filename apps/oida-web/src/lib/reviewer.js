export function isAiGuidanceCurrent(packet, guidance) {
  return Boolean(packet?.evidence_packet_hash && guidance?.evidence_packet_hash
    && packet.evidence_packet_hash === guidance.evidence_packet_hash
    && (!guidance.impact_context_hash || packet.impact_context_hash === guidance.impact_context_hash));
}

export function validCitations(packet, evidenceIds) {
  const allowed = new Set((packet?.evidence_items || []).map((item) => item.evidence_id));
  return (evidenceIds || []).filter((id) => allowed.has(id));
}

export function aiDisplayState({ guidance, busy, current }) {
  if (busy) return "LOADING";
  if (!guidance) return "IDLE";
  if (guidance.status !== "AVAILABLE") return "UNAVAILABLE";
  return current ? "READY" : "STALE";
}

export function canRetryAi(guidance, busy = false) {
  return Boolean(guidance && guidance.status !== "AVAILABLE" && !busy);
}

export function impactSections(impact) {
  return {
    known: impact?.known_impacts || [],
    suggested: impact?.ai_suggested_impacts || [],
    unknown: impact?.unknown || [],
  };
}

export function canReviewRelationship(relationship) {
  return ["AI_SUGGESTED", "UNKNOWN"].includes(relationship?.relationship_class);
}

export function effectiveImpactContext(review) {
  if (!review) return "NOT_REVIEWED";
  if (review.stale || review.human_review_status === "STALE") return "STALE";
  return review.decision === "CONFIRMED" ? "HUMAN_CONFIRMED" : review.decision;
}

export function routedActionForReview(review) {
  if (!review || effectiveImpactContext(review) !== "HUMAN_CONFIRMED") return null;
  const target = review.origin_relationship?.target_id;
  if (target === "UNRESOLVED:PM") return "ROUTE_PM_DELIVERY_HANDOFF";
  if (target === "UNRESOLVED:QA") return "ROUTE_QA_VALIDATION_HANDOFF";
  return null;
}
