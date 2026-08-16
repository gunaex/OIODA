"""Portable evidence package (rebuild prompt §17 "Portable Evidence
Package"). Built entirely server-side and in-memory:

- ZIP bytes assembled in an io.BytesIO — no filesystem temp files, so
  there's nothing to clean up (Phase 6 restatement's temp-file/cleanup
  strategy).
- Every evidence file is read via EvidenceStorage.get() — never a
  presigned URL, per the explicit requirement that the portable package
  must contain the actual bytes, not a link substitute (requirement 2).
- A missing object (see docs/EVIDENCE_STORAGE_LIFECYCLE.md) is recorded
  in the manifest as "missing": true and skipped, not a hard failure of
  the whole export — one bad row shouldn't block an otherwise-complete
  package.
"""

import io
import json
import re
import zipfile
from datetime import datetime, timezone

from . import models
from .report_excel import build_workbook, workbook_to_bytes, evidence_code
from .storage import EvidenceStorage


def _safe_slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", text.strip()).strip("-") or "item"


def _render_report_html(project: models.Project, cycle: models.TestCycle, counts: dict, pass_rate: dict) -> str:
    rows = "".join(f"<tr><td>{status}</td><td>{count}</td></tr>" for status, count in counts.items())
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{project.name} — {cycle.name}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #111; }}
  table {{ border-collapse: collapse; margin-top: 1rem; }}
  td, th {{ border: 1px solid #ccc; padding: 4px 10px; text-align: left; }}
  @media print {{ body {{ margin: 0.5in; }} }}
</style></head>
<body>
  <h1>{project.name}</h1>
  <h2>{cycle.name} &mdash; {cycle.environment}</h2>
  <p>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
  <h3>Result Summary</h3>
  <table><tr><th>Status</th><th>Count</th></tr>{rows}</table>
  <p>Pass rate: {pass_rate['percent']}% ({pass_rate['formula']})</p>
  <p>See the accompanying .xlsx for full detailed results, defects, evidence index, revision history, and sign-off records.</p>
</body></html>"""


def build_evidence_package(
    db,
    project: models.Project,
    cycle: models.TestCycle,
    storage: EvidenceStorage,
    generated_by: str,
) -> tuple[bytes, str]:
    """Returns (zip_bytes, filename)."""
    from .metrics import result_counts, pass_rate as pass_rate_fn

    wb = build_workbook(db, project, cycle, generated_by)
    xlsx_bytes = workbook_to_bytes(wb)

    cases_by_result = {
        r.id: c
        for r, c in (
            db.query(models.CycleTestResult, models.TestCase)
            .join(models.TestCase, models.TestCase.id == models.CycleTestResult.test_case_id)
            .filter(models.CycleTestResult.cycle_id == cycle.id)
            .all()
        )
    }
    evidence_items = db.query(models.EvidenceItem).filter(models.EvidenceItem.cycle_id == cycle.id).all()

    package_slug = f"{_safe_slug(project.slug)}_{_safe_slug(cycle.name)}"
    zip_buf = io.BytesIO()
    manifest_evidence = []

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{package_slug}.xlsx", xlsx_bytes)
        zf.writestr(
            "report.html",
            _render_report_html(project, cycle, result_counts(db, cycle.id), pass_rate_fn(db, cycle.id)),
        )

        for item in evidence_items:
            case = cases_by_result.get(item.cycle_test_result_id)
            test_id = _safe_slug(case.checkpoint_code) if case else "unknown"
            ext = item.object_key.rsplit(".", 1)[-1] if "." in item.object_key else "bin"
            filename = f"{test_id}_{evidence_code(item.id)}.{ext}"

            missing = False
            try:
                content = storage.get(item.object_key)
            except Exception:
                missing = True
                content = None

            archive_path = f"evidence/{filename}"
            if content is not None:
                zf.writestr(archive_path, content)

            manifest_evidence.append(
                {
                    "evidence_id": item.id,
                    "test_id": case.checkpoint_code if case else None,
                    # The exact in-archive path (not just a bare filename)
                    # so manifest.json -> zip entry lookup is a direct
                    # match, no prefix-guessing required by a consumer.
                    "filename": archive_path if not missing else None,
                    "sha256": item.original_sha256,
                    "size_bytes": item.original_size_bytes,
                    "status": item.status,
                    "captured_by": item.captured_by,
                    "captured_at": item.captured_at.isoformat() if item.captured_at else None,
                    "annotation_revision": item.current_revision_no,
                    "missing": missing,
                }
            )

        manifest = {
            "package_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": generated_by,
            "project": {"slug": project.slug, "name": project.name},
            "cycle": {
                "id": cycle.id,
                "name": cycle.name,
                "environment": cycle.environment,
                "status": cycle.status,
            },
            "evidence": manifest_evidence,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    return zip_buf.getvalue(), f"{package_slug}_evidence_package.zip"
