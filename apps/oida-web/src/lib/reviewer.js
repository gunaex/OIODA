export function isAiGuidanceCurrent(packet, guidance) {
  return Boolean(packet?.evidence_packet_hash && guidance?.evidence_packet_hash
    && packet.evidence_packet_hash === guidance.evidence_packet_hash);
}

export function validCitations(packet, evidenceIds) {
  const allowed = new Set((packet?.evidence_items || []).map((item) => item.evidence_id));
  return (evidenceIds || []).filter((id) => allowed.has(id));
}
