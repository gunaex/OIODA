"""R17 — Applicability Engine (deterministic rules, explainable).

The engine resolves every standard to exactly one applicability state for a
project profile, with a human-readable reason. AI may only recommend changes;
the final applicability is rule-derived and may only be changed by a human
override recorded on the deliverable instance.
"""

from __future__ import annotations

from .standards import STANDARDS
from .taxonomy import APPLICABILITY_STATES

TRUTHY_ATTRIBUTE_VALUES = (True, "true", "TRUE", "HIGH", "yes", 1)


def _attr_true(profile: dict, key: str) -> bool:
    return profile.get("attributes", {}).get(key) in TRUTHY_ATTRIBUTE_VALUES


def apply_special_rules(code: str, standard: dict, profile: dict) -> tuple[str, str] | None:
    """Return (applicability, reason) for a special rule, or None."""
    primary_type = (profile.get("primary_type") or "").upper()
    workstreams = {w.upper() for w in profile.get("workstreams", [])}
    attributes = profile.get("attributes", {})

    # POC/PILOT: operational handover is optional.
    if primary_type == "POC_PILOT" and standard["name"] == "Operational Handover":
        return ("OPTIONAL", "primary_type=POC_PILOT: operational handover is optional")

    # Infrastructure + high production impact forces a rollback plan.
    if (
        standard["name"] == "Rollback Plan"
        and "INFRASTRUCTURE" in workstreams
        and str(attributes.get("production_impact", "")).upper() == "HIGH"
    ):
        return ("MANDATORY", "workstream=INFRASTRUCTURE AND production_impact=HIGH")

    return None


def evaluate_standard(code: str, standard: dict, profile: dict) -> dict:
    special = apply_special_rules(code, standard, profile)
    if special:
        applicability, reason = special
        return {"code": code, "applicability": applicability, "reason": [reason]}

    if standard["domain"] == "CORE":
        return {
            "code": code,
            "applicability": "MANDATORY",
            "reason": ["core universal project deliverable"],
        }

    profile_workstreams = {w.upper() for w in profile.get("workstreams", [])}
    matched_ws = [w for w in standard["workstreams"] if w.upper() in profile_workstreams]
    matched_attrs = [a for a in standard["attributes"] if _attr_true(profile, a)]

    if matched_ws:
        return {
            "code": code,
            "applicability": standard["workstream_strength"],
            "reason": [f"workstream={w}" for w in matched_ws],
        }
    if matched_attrs:
        return {
            "code": code,
            "applicability": "MANDATORY",
            "reason": [f"attribute={a}" for a in matched_attrs],
        }
    return {
        "code": code,
        "applicability": "NOT_APPLICABLE",
        "reason": ["no driving workstream or attribute in project profile"],
    }


def evaluate_profile(profile: dict) -> list[dict]:
    """Resolve the full applicability matrix for a project profile."""
    rows = []
    for code, standard in STANDARDS.items():
        ev = evaluate_standard(code, standard, profile)
        rows.append({
            "code": code,
            "name": standard["name"],
            "domain": standard["domain"],
            "category": standard["category"],
            "applicability": ev["applicability"],
            "reason": ev["reason"],
            "layout_template": standard["layout_template"],
            "template_version": standard["template_version"],
            "owner_role": standard["owner_role"],
            "approver_roles": standard["approver_roles"],
            "source_authorities": standard["source_authorities"],
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    counts = {s: 0 for s in APPLICABILITY_STATES}
    for r in rows:
        counts[r["applicability"]] = counts.get(r["applicability"], 0) + 1
    return {
        "total": len(rows),
        "by_applicability": counts,
        "by_domain": _count_by(rows, "domain"),
        "by_category": _count_by(rows, "category"),
    }


def _count_by(rows: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out
