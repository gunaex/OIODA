"""
Compares QA Again's vendored canonical contracts (app/contracts/vendored/)
against the live AGAIN-ECOSYSTEM source repository, to detect drift between
what QA Again validates against and what the canonical authority now
declares.

Usage:
    python scripts/check_contract_drift.py [--source-repo PATH]

Exit code 0 = no drift. Exit code 1 = drift detected or source repo missing
(source repo absence is reported, not silently ignored).
"""

import argparse
import json
import sys
from pathlib import Path

VENDORED_DIR = Path(__file__).parent.parent / "app" / "contracts" / "vendored"


def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", default="/Users/kanphong/AGAIN-ECOSYSTEM")
    args = parser.parse_args()

    source_repo = Path(args.source_repo)
    manifest = _load_json(VENDORED_DIR / "manifest.json")

    if not source_repo.exists():
        print(f"DRIFT_CHECK=SKIPPED (source repo not found at {source_repo})")
        return 1

    drift_found = False
    for version_key in ("v1", "v2"):
        contracts = manifest[version_key]["contracts"]
        for name in contracts:
            vendored_path = VENDORED_DIR / version_key / "schemas" / f"{name}.json"
            source_path = source_repo / "contracts" / version_key / "schemas" / f"{name}.json"

            if not source_path.exists():
                print(f"DRIFT: {version_key}/{name} missing from source repo at {source_path}")
                drift_found = True
                continue

            vendored = _load_json(vendored_path)
            source = _load_json(source_path)
            if vendored != source:
                print(f"DRIFT: {version_key}/{name} differs from canonical source ({source_path})")
                drift_found = True

    if drift_found:
        print("CONTRACT_DRIFT_DETECTABLE=PASS (drift found — re-vendor required)")
        return 1

    print(f"CONTRACT_DRIFT_DETECTABLE=PASS (no drift vs {manifest['sourceCommit']} content)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
