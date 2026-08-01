import { readFileSync } from "node:fs";
import type { RunnerConfig } from "../env.js";

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
}

export interface HybridRunDetail extends HybridRun {
  events: Array<{ id: number; event_type: string; actor_type: string; payload_json: string | null; created_at: string }>;
  latest_decision: { decision: string; reason: string | null; decided_by: string; decided_at: string } | null;
}

export class QaAgainClient {
  private base: string;
  private slug: string;
  private token: string;

  constructor(config: RunnerConfig) {
    this.base = `${config.backendBaseUrl}/api/${config.projectSlug}/hybrid/runs`;
    this.slug = config.projectSlug;
    this.token = config.runnerToken;
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
    return this.request<HybridRun>("", { method: "POST", body: JSON.stringify({ label }) });
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
