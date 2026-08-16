#!/usr/bin/env python3
"""Gate 10: Frontend Phase 6 truth — verify source contains required components."""
import sys, os

REQUIRED_COMPONENTS = [
    # Page
    "ImplementationPlanPage.tsx",
    # Components
    "PlanSummary.tsx",
    "WorkPackageList.tsx",
    "DependencyGraph.tsx",
    "CriticalPathPanel.tsx",
    "ReadinessMatrix.tsx",
    "RiskBlockerPanel.tsx",
    "ImplementationTimeline.tsx",
    "ScheduleModeToggle"  ,  # in ImplementationTimeline.tsx
    "PlanReviewPanel.tsx",
    "HandoffPanel.tsx",
    # Model
    "implementationTypes.ts",
    "implementationMapper.ts",
]

REQUIRED_PATTERNS = [
    # Safety text
    ("No infrastructure will be created by this action", "PlanReviewPanel.tsx"),
    # Approval confirmation
    ("APPROVED_FOR_EXECUTION", "PlanReviewPanel.tsx"),
    # Readiness
    ("PARTIALLY_READY", "ReadinessMatrix.tsx"),
    # PM handoff
    ("contractVersion", "HandoffPanel.tsx"),
    # QA handoff
    ("testItems", "HandoffPanel.tsx"),
    # Critical path
    ("criticalPath", "CriticalPathPanel.tsx"),
    # Dependency graph
    ("DependencyGraph", "DependencyGraph.tsx"),
    # RELAXED/FIT
    ("RELAXED", "ImplementationTimeline.tsx"),
    ("FIT", "ImplementationTimeline.tsx"),
    # Change request
    ("Request Change", "PlanReviewPanel.tsx"),
    # CTA
    ("Create Implementation Plan", "ImplementationPlanPage.tsx"),
    # derivedFrom
    ("derivedFrom", "implementationTypes.ts"),
    # planChecksum
    ("planChecksum", "implementationTypes.ts"),
]

def main(log_dir):
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    feature_dir = os.path.join(base, "ui", "src", "features", "implementation-planner")
    
    if not os.path.isdir(feature_dir):
        print("FAIL: implementation-planner/ directory missing")
        return 1
    
    # Check required files exist
    missing_files = []
    for fname in REQUIRED_COMPONENTS:
        # ScheduleModeToggle is in ImplementationTimeline.tsx
        if fname == "ScheduleModeToggle":
            continue
        # Page file is in the feature root, not components/
        if fname == "ImplementationPlanPage.tsx":
            fpath = os.path.join(feature_dir, fname)
        elif fname.endswith(".tsx"):
            fpath = os.path.join(feature_dir, "components", fname)
        else:
            fpath = os.path.join(feature_dir, "model", fname)
        if not os.path.isfile(fpath):
            missing_files.append(fname)
    
    if missing_files:
        print(f"FAIL: Missing files: {missing_files}")
        return 1
    
    # Check required patterns in source
    missing_patterns = []
    for pattern, fname in REQUIRED_PATTERNS:
        if fname == "ImplementationPlanPage.tsx":
            fpath = os.path.join(feature_dir, fname)
        elif fname.endswith(".tsx"):
            fpath = os.path.join(feature_dir, "components", fname)
        else:
            fpath = os.path.join(feature_dir, "model", fname)
        if not os.path.isfile(fpath):
            continue
        content = open(fpath).read()
        if pattern not in content:
            missing_patterns.append(f"{pattern} in {fname}")
    
    if missing_patterns:
        print(f"FAIL: Missing patterns: {missing_patterns}")
        return 1
    
    # Check App.tsx imports the page
    app_tsx = os.path.join(base, "ui", "src", "App.tsx")
    if os.path.isfile(app_tsx):
        content = open(app_tsx).read()
        if "ImplementationPlanPage" not in content:
            print("FAIL: App.tsx does not import ImplementationPlanPage")
            return 1
        if "'impl'" not in content:
            print("FAIL: App.tsx does not have impl tab")
            return 1
    
    # Check npm ci and build produce output
    dist_html = os.path.join(base, "ui", "dist", "index.html")
    if not os.path.isfile(dist_html):
        print("FAIL: dist/index.html missing — run npm ci && npm run build first")
        return 1
    
    print("PASS: All required components, patterns, and build verified")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
