"""Deterministic metadata-only license policy classification."""

from __future__ import annotations

import re
from dataclasses import dataclass

from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.models.policy import ALLOWED_RETRIEVABLE_LICENSE_IDS

_SPDX_RE = re.compile(
    r"(?im)^\s*(?:SPDX-License-Identifier|License)\s*:\s*([A-Za-z0-9.()+-]+)"
)
_COPYRIGHT_RE = re.compile(r"(?im)^\s*copyright\b.{0,180}")


@dataclass(frozen=True)
class LicensePolicyFinding:
    """Safe license finding metadata without full raw file content."""

    scanner_name: str
    scanner_version: str
    license_expression: str | None
    license_id: str | None
    copyright_notice: str | None
    finding_location: str | None
    confidence: float | None
    policy_status: str


def classify_license_policy(
    *,
    text: str | None,
    configured_policy_status: str,
    locator: str,
) -> LicensePolicyFinding:
    """Classify license policy using deterministic local metadata only."""

    license_id = _extract_license_id(text)
    policy_status = configured_policy_status
    if license_id is not None:
        policy_status = (
            "allowed"
            if license_id in ALLOWED_RETRIEVABLE_LICENSE_IDS
            else "review_required"
        )

    return LicensePolicyFinding(
        scanner_name="builtin-license-policy",
        scanner_version="mvp-3.7",
        license_expression=license_id,
        license_id=license_id,
        copyright_notice=_extract_safe_copyright(text),
        finding_location=sanitize_diagnostic_text(locator),
        confidence=0.95 if license_id is not None else None,
        policy_status=policy_status,
    )


def _extract_license_id(text: str | None) -> str | None:
    if not text:
        return None
    match = _SPDX_RE.search(text)
    if match is None:
        return None
    return match.group(1)[:100]


def _extract_safe_copyright(text: str | None) -> str | None:
    if not text:
        return None
    match = _COPYRIGHT_RE.search(text)
    if match is None:
        return None
    return sanitize_diagnostic_text(match.group(0))
