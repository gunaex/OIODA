import test from "node:test";
import assert from "node:assert/strict";
import { aiDisplayState, canRetryAi, canReviewRelationship, effectiveImpactContext, impactSections, isAiGuidanceCurrent, routedActionForReview, validCitations } from "./reviewer.js";

test("AI guidance is current only for the exact evidence hash", () => {
  assert.equal(isAiGuidanceCurrent({ evidence_packet_hash: "a" }, { evidence_packet_hash: "a" }), true);
  assert.equal(isAiGuidanceCurrent({ evidence_packet_hash: "b" }, { evidence_packet_hash: "a" }), false);
  assert.equal(isAiGuidanceCurrent({ evidence_packet_hash: "a" }, null), false);
  assert.equal(isAiGuidanceCurrent(
    { evidence_packet_hash: "a", impact_context_hash: "i2" },
    { evidence_packet_hash: "a", impact_context_hash: "i1" }), false);
});

test("unknown evidence citations are not resolved by the UI", () => {
  const packet = { evidence_items: [{ evidence_id: "E-001" }, { evidence_id: "E-002" }] };
  assert.deepEqual(validCitations(packet, ["E-001", "E-999", "E-002"]), ["E-001", "E-002"]);
});

test("AI display state keeps loading, failure, success, and stale guidance distinct", () => {
  assert.equal(aiDisplayState({ busy: true }), "LOADING");
  assert.equal(aiDisplayState({ guidance: null, busy: false }), "IDLE");
  assert.equal(aiDisplayState({ guidance: { status: "TIMEOUT" }, busy: false }), "UNAVAILABLE");
  assert.equal(aiDisplayState({ guidance: { status: "AVAILABLE" }, busy: false, current: false }), "STALE");
  assert.equal(aiDisplayState({ guidance: { status: "AVAILABLE" }, busy: false, current: true }), "READY");
});

test("manual retry is offered only after failure", () => {
  assert.equal(canRetryAi({ status: "TIMEOUT" }), true);
  assert.equal(canRetryAi({ status: "MALFORMED" }), true);
  assert.equal(canRetryAi({ status: "AVAILABLE" }), false);
  assert.equal(canRetryAi(null), false);
});

test("impact sections never merge known, suggested, and unknown truth", () => {
  const sections = impactSections({
    known_impacts: [{ impact_id: "K1" }],
    ai_suggested_impacts: [{ impact_id: "A1" }],
    unknown: [{ domain: "QA" }],
  });
  assert.deepEqual(sections.known.map((x) => x.impact_id), ["K1"]);
  assert.deepEqual(sections.suggested.map((x) => x.impact_id), ["A1"]);
  assert.deepEqual(sections.unknown.map((x) => x.domain), ["QA"]);
});

test("only advisory or unknown relationships enter human relationship review", () => {
  assert.equal(canReviewRelationship({ relationship_class: "AI_SUGGESTED" }), true);
  assert.equal(canReviewRelationship({ relationship_class: "UNKNOWN" }), true);
  assert.equal(canReviewRelationship({ relationship_class: "EXPLICIT" }), false);
  assert.equal(canReviewRelationship({ relationship_class: "DETERMINISTIC" }), false);
});

test("human confirmation is an effective context without rewriting origin", () => {
  assert.equal(effectiveImpactContext(null), "NOT_REVIEWED");
  assert.equal(effectiveImpactContext({ decision: "CONFIRMED", stale: false }), "HUMAN_CONFIRMED");
  assert.equal(effectiveImpactContext({ decision: "REJECTED", stale: false }), "REJECTED");
  assert.equal(effectiveImpactContext({ decision: "CONFIRMED", stale: true }), "STALE");
});

test("controlled routing is allowlisted only for current human-confirmed PM or QA context", () => {
  const base = { decision: "CONFIRMED", stale: false };
  assert.equal(routedActionForReview({ ...base, origin_relationship: { target_id: "UNRESOLVED:PM" } }), "ROUTE_PM_DELIVERY_HANDOFF");
  assert.equal(routedActionForReview({ ...base, origin_relationship: { target_id: "UNRESOLVED:QA" } }), "ROUTE_QA_VALIDATION_HANDOFF");
  assert.equal(routedActionForReview({ ...base, origin_relationship: { target_id: "UNRESOLVED:INFRA" } }), null);
  assert.equal(routedActionForReview({ ...base, stale: true, origin_relationship: { target_id: "UNRESOLVED:QA" } }), null);
});
