"""R17 — Layout Template Registry + Brand Profile.

Layouts and branding are separated from the deliverable standard schema so a
customer or joint-branding project can reuse the same standards with a
different brand.
"""

from __future__ import annotations

# code -> (name, version, purpose, orientation)
LAYOUTS = {
    "LAYOUT-COVER-001": ("Cover", "1.0", "Document cover (enterprise, print friendly)", "portrait"),
    "LAYOUT-DOCCTRL-001": ("Document Control", "1.0", "Document control sheet", "portrait"),
    "LAYOUT-REVISION-001": ("Revision History", "1.0", "Revision history table", "portrait"),
    "LAYOUT-INDEX-001": ("Sheet Index", "1.0", "Clickable sheet index", "portrait"),
    "LAYOUT-REGISTER-001": ("Register", "1.0", "Generic register (ID/title/status/owner…)", "landscape"),
    "LAYOUT-MATRIX-001": ("Matrix", "1.0", "Traceability / dependency / access matrix", "landscape"),
    "LAYOUT-DESIGN-001": ("Design", "1.0", "Design summary (narrative + tables)", "landscape"),
    "LAYOUT-RUNBOOK-001": ("Runbook", "1.0", "Step-based runbook (step/phase/validation/rollback)", "landscape"),
    "LAYOUT-RISK-001": ("Risk Register", "1.0", "Risk / vulnerability / issue register", "landscape"),
    "LAYOUT-TEST-001": ("Test", "1.0", "Test plan / result register", "landscape"),
    "LAYOUT-SIGNOFF-001": ("Sign-off", "1.0", "Review / approval sign-off", "portrait"),
    "LAYOUT-SOURCE-001": ("Source Reference", "1.0", "Provenance / source-authority reference", "landscape"),
}


def layout_registry() -> list[dict]:
    return [
        {
            "code": code,
            "name": name,
            "version": version,
            "purpose": purpose,
            "orientation": orientation,
        }
        for code, (name, version, purpose, orientation) in LAYOUTS.items()
    ]


def get_layout(code: str) -> dict | None:
    if code not in LAYOUTS:
        return None
    name, version, purpose, orientation = LAYOUTS[code]
    return {"code": code, "name": name, "version": version, "purpose": purpose, "orientation": orientation}


# ── Brand profiles ──────────────────────────────────────────────────────────
BRAND_PROFILES = {
    "GEA_STANDARD": {
        "name": "GEA_STANDARD",
        "company_name": "Global Edge",
        "classification_default": "Confidential",
        "style_profile": "corporate",
        "logo": None,
        "colors": {
            "primary": "1F4E78",      # navy
            "secondary": "D9EAF7",    # pale blue
            "neutral": "F3F4F6",      # pale gray
            "border": "D1D5DB",
            "accent": "2E75B6",
        },
    },
    "CUSTOMER_STANDARD": {
        "name": "CUSTOMER_STANDARD",
        "company_name": None,
        "classification_default": "Confidential",
        "style_profile": "corporate",
        "logo": None,
        "colors": {
            "primary": "1F4E78",
            "secondary": "E8EEF4",
            "neutral": "F5F6F8",
            "border": "C9CED4",
            "accent": "2E75B6",
        },
    },
    "JOINT_BRANDING": {
        "name": "JOINT_BRANDING",
        "company_name": None,
        "classification_default": "Confidential",
        "style_profile": "corporate",
        "logo": None,
        "colors": {
            "primary": "1F4E78",
            "secondary": "D9EAF7",
            "neutral": "F3F4F6",
            "border": "D1D5DB",
            "accent": "2E75B6",
        },
    },
}


def get_brand(name: str = "GEA_STANDARD") -> dict:
    return BRAND_PROFILES.get(name, BRAND_PROFILES["GEA_STANDARD"])
