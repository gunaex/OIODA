import test from "node:test";
import assert from "node:assert/strict";
import { request, resolveApiBase } from "../api/client.js";

test("production hostname falls back to the gateway when build metadata is missing", () => {
  assert.equal(resolveApiBase("", "oida.kanphong.com"), "https://api-oida.kanphong.com");
  assert.equal(resolveApiBase("", "localhost"), "");
  assert.equal(resolveApiBase("https://example.test/", "oida.kanphong.com"), "https://example.test");
});

test("SPA HTML can never be accepted as successful API truth", async () => {
  const originalFetch = globalThis.fetch;
  const originalStorage = globalThis.localStorage;
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true, value: { getItem: () => null },
  });
  globalThis.fetch = async () => new Response("<!doctype html><div id=\"root\"></div>", {
    status: 200, headers: { "content-type": "text/html" },
  });
  try {
    await assert.rejects(() => request("auth", "/me"), /Unexpected non-JSON response/);
  } finally {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true, value: originalStorage,
    });
  }
});
