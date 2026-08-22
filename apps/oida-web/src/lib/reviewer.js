export function isAiGuidanceCurrent(packet, guidance) {
  return Boolean(packet?.evidence_packet_hash && guidance?.evidence_packet_hash
    && packet.evidence_packet_hash === guidance.evidence_packet_hash);
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
