import test from "node:test";
import assert from "node:assert/strict";
import { isAiGuidanceCurrent, validCitations } from "./reviewer.js";

test("AI guidance is current only for the exact evidence hash", () => {
  assert.equal(isAiGuidanceCurrent({ evidence_packet_hash: "a" }, { evidence_packet_hash: "a" }), true);
  assert.equal(isAiGuidanceCurrent({ evidence_packet_hash: "b" }, { evidence_packet_hash: "a" }), false);
  assert.equal(isAiGuidanceCurrent({ evidence_packet_hash: "a" }, null), false);
});

test("unknown evidence citations are not resolved by the UI", () => {
  const packet = { evidence_items: [{ evidence_id: "E-001" }, { evidence_id: "E-002" }] };
  assert.deepEqual(validCitations(packet, ["E-001", "E-999", "E-002"]), ["E-001", "E-002"]);
});
