import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import type { RunnerConfig } from "../env.js";

const require = createRequire(import.meta.url);
// Read directly from package.json rather than hard-coding a version
// string that would drift from the real one (QA-E7.1: runnerVersion must
// be what the runner actually is, not an assumed constant).
const RUNNER_VERSION: string = require("../../package.json").version;
// One instance id per process — distinguishes concurrent runner
// processes sharing the same RunnerToken (QA-E7.1).
const RUNNER_INSTANCE_ID = randomUUID();

// Every call here is outbound: the runner initiates every request to the
// backend. The backend never calls into the runner or the tester's
// machine — see docs/hybrid/HYB-0-GAP-ANALYSIS.md section 6 ("minimum
// contract") for why, and gate criterion 3 ("outbound-only").

export type RunnerEventType =
  | "RUN_CLAIMED"
  | "STEP_STARTED"
  | "STEP_COMPLETED"
  | "CHECKPOINT_WAITING"
  | "CHECKPOINT_RELEASED"
  | "EVIDENCE_UPLOADED"
  | "RUN_COMPLETED";

export interface HybridRun {
  id: number;
  status: string;
  label: string | null;
  started_at: string;
  ended_at: string | null;
  created_at: string;
  runner_token_id: number | null;
  runner_label: string | null;
  runner_instance_id: string | null;
  runner_version: string | null;
  external_qa_request_id: string | null;
  correlation_id: string | null;
  test_cycle_id: number | null;
  cycle_test_result_id: number | null;
  environment: string | null;
  target_base_url: string | null;
  artifact_ref: string | null;
  browser_name: string | null;
  browser_version: string | null;
  os_platform: string | null;
}

export interface HybridRunDetail extends HybridRun {
  events: Array<{ id: number; event_type: string; actor_type: string; payload_json: string | null; created_at: string }>;
  latest_decision: { decision: string; reason: string | null; decided_by: string; decided_at: string } | null;
}

export class QaAgainClient {
  private base: string;
  private slug: string;
  private token: string;
  private config: RunnerConfig;

  constructor(config: RunnerConfig) {
    this.base = `${config.backendBaseUrl}/api/${config.projectSlug}/hybrid/runs`;
    this.slug = config.projectSlug;
    this.token = config.runnerToken;
    this.config = config;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await fetch(`${this.base}${path}`, {
      ...init,
      headers: {
        "X-Runner-Token": this.token,
        ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`${init.method ?? "GET"} ${path} -> ${res.status}: ${body}`);
    }
    return (await res.json()) as T;
  }

  createRun(label: string): Promise<HybridRun> {
    return this.request<HybridRun>("", {
      method: "POST",
      body: JSON.stringify({
        label,
        runner_instance_id: RUNNER_INSTANCE_ID,
        runner_version: RUNNER_VERSION,
        test_cycle_id: this.config.testCycleId,
        cycle_test_result_id: this.config.cycleTestResultId,
        external_qa_request_id: this.config.externalQaRequestId,
        correlation_id: this.config.correlationId,
        environment: this.config.environment,
        target_base_url: this.config.targetBaseUrl,
        artifact_ref: this.config.artifactRef,
      }),
    });
  }

  /** QA-E7.4 — reports real browser identity once Playwright has
   * actually launched a browser. Never called with assumed/hard-coded
   * values — see browser/spike.ts. */
  reportProvenance(
    runId: number,
    provenance: { browser_name?: string; browser_version?: string; os_platform?: string },
  ): Promise<HybridRun> {
    return this.request<HybridRun>(`/${runId}/provenance`, {
      method: "PATCH",
      body: JSON.stringify(provenance),
    });
  }

  postEvent(runId: number, eventType: RunnerEventType, payload?: unknown): Promise<unknown> {
    return this.request(`/${runId}/events`, {
      method: "POST",
      body: JSON.stringify({
        event_type: eventType,
        actor_type: "RUNNER",
        payload_json: payload ? JSON.stringify(payload) : undefined,
      }),
    });
  }

  getRun(runId: number): Promise<HybridRunDetail> {
    return this.request<HybridRunDetail>(`/${runId}`);
  }

  async uploadEvidence(runId: number, filePath: string, filename: string): Promise<unknown> {
    const fileBuffer = readFileSync(filePath);
    const form = new FormData();
    form.append("file", new Blob([fileBuffer], { type: "image/png" }), filename);
    return this.request(`/${runId}/evidence`, { method: "POST", body: form });
  }

  finishRun(runId: number): Promise<HybridRun> {
    return this.request<HybridRun>(`/${runId}/finish`, { method: "POST" });
  }

  /** Polls until the run leaves WAITING_FOR_HUMAN. Simplest correct
   * approach for a spike (see gap analysis decision 1) — no WebSocket. */
  async waitForHumanDecision(runId: number, pollIntervalMs = 2000, timeoutMs = 5 * 60_000): Promise<HybridRunDetail> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const run = await this.getRun(runId);
      if (run.status !== "WAITING_FOR_HUMAN") {
        return run;
      }
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }
    throw new Error(`Timed out waiting for a human checkpoint decision on run ${runId}`);
  }
}
