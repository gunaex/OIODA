import test from "node:test";
import assert from "node:assert/strict";
import { buildOwnerLinks } from "./ownerLinks.js";

const truth = { bindings: {
  pm: { binding_status: "BOUND", external_project_id: "pm project" },
  qa: [{ binding_status: "BOUND", external_project_id: "qa/project" }],
  infra: { binding_status: "BOUND", external_project_id: "design-1" },
} };

test("builds only known routes when auth continuity is explicit", () => {
  const links = buildOwnerLinks(truth, { authContinuity: true,
    pmBase: "https://pm.example", qaBase: "https://qa.example" });
  assert.equal(links.pm, "https://pm.example/pm%20project/gantt");
  assert.equal(links.qa, "https://qa.example/qa%2Fproject/dashboard");
  assert.equal(links.infra, null);
});

test("does not fabricate links without a binding or auth continuity", () => {
  assert.deepEqual(buildOwnerLinks(truth, { authContinuity: false,
    pmBase: "https://pm.example", qaBase: "https://qa.example" }), { pm: null, qa: null, infra: null });
  assert.deepEqual(buildOwnerLinks({ bindings: { pm: {}, qa: [] } }, { authContinuity: true,
    pmBase: "https://pm.example", qaBase: "https://qa.example" }), { pm: null, qa: null, infra: null });
});

test("rejects invalid or credential-bearing route metadata", () => {
  const links = buildOwnerLinks(truth, { authContinuity: true,
    pmBase: "javascript:alert(1)", qaBase: "https://user:secret@qa.example" });
  assert.deepEqual(links, { pm: null, qa: null, infra: null });
});
