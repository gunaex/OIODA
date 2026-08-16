# P4 — Performance Budgets (documented limits from actual build output)

Measured with a production `vite build` (rolldown, gzip columns below).
Budgets are set at ~2× current observed output to catch regressions without
forcing premature micro-optimization. `BUNDLE_BUDGET=PASS` when all chunks
stay under budget.

## Observed output (commit 7a1125d)

| Chunk | Size | gzip | Budget | Status |
|---|---|---|---|---|
| main initial JS (`index`) | 255.63 kB | 80.34 kB | ≤ 320 kB | PASS |
| editor chunk (`Artifacts`, Tiptap) | 449.03 kB | 140.98 kB | ≤ 520 kB | PASS |
| ERD chunk (`Database`) | 20.62 kB | 5.05 kB | ≤ 80 kB | PASS |
| flow chunk (`FlowDesigner`) | 8.49 kB | 2.52 kB | ≤ 40 kB | PASS |
| architecture chunk | 8.72 kB | 2.56 kB | ≤ 40 kB | PASS |
| React Flow shared (`style-*.js`) | 175.56 kB | 56.65 kB | ≤ 220 kB | PASS |
| largest lazy chunk | 449.03 kB | — | ≤ 520 kB | PASS |

## API performance checks (representative, not a benchmark)

Run against the P4 dogfood dataset (a few dozen objects) via
`scripts/api_perf_smoke.py` — reported as timings, not production
benchmarks. Representative timings (single run, local SQLite, dev machine)
are printed by that script; thresholds are advisory only.

## Notes

- React Flow is code-split into one shared chunk shared by ERD / Flow /
  Architecture, so per-page chunks stay small.
- The editor (Tiptap) is the dominant cost and is lazily loaded only when a
  UR/DR workspace is opened.
