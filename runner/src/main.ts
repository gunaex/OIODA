import { loadConfig } from "./env.js";
import { runSpike } from "./browser/spike.js";

const config = loadConfig();
runSpike(config).catch((err) => {
  console.error("[runner] spike failed:", err);
  process.exitCode = 1;
});
