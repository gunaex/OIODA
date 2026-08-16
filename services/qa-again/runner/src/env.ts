import { readFileSync, existsSync } from "node:fs";

// Deliberately no `dotenv` dependency — a spike stays small. Loads
// `.env` next to package.json if present; real env vars always win.
export function loadDotEnv(path = ".env"): void {
  if (!existsSync(path)) return;
  const contents = readFileSync(path, "utf-8");
  for (const rawLine of contents.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    if (process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

export interface RunnerConfig {
  backendBaseUrl: string;
  projectSlug: string;
  runnerToken: string;
  targetBaseUrl: string;
  targetEmail: string;
  targetPassword: string;
  // QA-E7 provenance — all optional. HYB-0's own spike scenario isn't
  // tied to a published TestCycle/TestCase, so these stay undefined
  // unless an operator running against a real published revision sets
  // them; the backend records "unknown" honestly rather than a guess.
  testCycleId?: number;
  cycleTestResultId?: number;
  externalQaRequestId?: string;
  correlationId?: string;
  environment?: string;
  artifactRef?: string;
}

export function loadConfig(): RunnerConfig {
  loadDotEnv();
  const required = (name: string): string => {
    const value = process.env[name];
    if (!value) {
      throw new Error(`Missing required env var ${name} (see .env.example)`);
    }
    return value;
  };
  const optionalInt = (name: string): number | undefined => {
    const value = process.env[name];
    if (!value) return undefined;
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? undefined : parsed;
  };
  return {
    backendBaseUrl: required("BACKEND_BASE_URL"),
    projectSlug: required("PROJECT_SLUG"),
    runnerToken: required("RUNNER_TOKEN"),
    targetBaseUrl: required("TARGET_BASE_URL"),
    targetEmail: required("TARGET_EMAIL"),
    targetPassword: required("TARGET_PASSWORD"),
    testCycleId: optionalInt("TEST_CYCLE_ID"),
    cycleTestResultId: optionalInt("CYCLE_TEST_RESULT_ID"),
    externalQaRequestId: process.env.EXTERNAL_QA_REQUEST_ID || undefined,
    correlationId: process.env.CORRELATION_ID || undefined,
    environment: process.env.QA_ENVIRONMENT || undefined,
    artifactRef: process.env.ARTIFACT_REF || undefined,
  };
}
