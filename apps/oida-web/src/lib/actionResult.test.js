import test from "node:test";
import assert from "node:assert/strict";
import { impactResolutionFromActionResult } from "./actionResult.js";

test("reads the backend impact_resolution contract after owner action", () => {
  const waiting = { resolution_state: "WAITING_ON_OWNER" };
  assert.equal(impactResolutionFromActionResult({ status: "SUCCEEDED", impact_resolution: waiting }), waiting);
  assert.equal(impactResolutionFromActionResult({ status: "SUCCEEDED" }), null);
});
