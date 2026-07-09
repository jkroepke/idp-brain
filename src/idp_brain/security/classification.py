"""Deterministic sensitivity classification for sanitized extraction candidates."""

from __future__ import annotations

from collections.abc import Iterable

from idp_brain.security.redaction import RedactionFinding

_SENSITIVITY_RANK = {
    "unknown": 0,
    "public": 1,
    "internal": 2,
    "confidential": 3,
    "restricted": 4,
}


def classify_sanitized_candidate(
    *,
    existing_sensitivity_class: str,
    findings: Iterable[RedactionFinding],
) -> str:
    """Return the highest deterministic sensitivity class implied by findings."""

    target = existing_sensitivity_class
    for finding in findings:
        if finding.redaction_type == "secret":
            target = _max_sensitivity(target, "restricted")
        elif finding.redaction_type == "pii":
            target = _max_sensitivity(target, "confidential")
    return target


def _max_sensitivity(current: str, candidate: str) -> str:
    if _SENSITIVITY_RANK.get(candidate, 0) > _SENSITIVITY_RANK.get(current, 0):
        return candidate
    return current
