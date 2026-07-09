"""Deterministic local redaction scanners."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from idp_brain.config.models import RedactionRuleConfig, SecurityConfig


@dataclass(frozen=True)
class RedactionRule:
    """Compiled redaction rule that never stores matched values."""

    rule_id: str
    redaction_type: str
    severity: str
    pattern: re.Pattern[str]
    scanner_name: str = "builtin-redactor"
    scanner_version: str = "mvp-3.7"


@dataclass(frozen=True)
class RedactionFinding:
    """Safe redaction result metadata."""

    rule_id: str
    redaction_type: str
    marker: str
    count: int
    confidence: float
    scanner_name: str
    scanner_version: str
    severity: str


class Redactor:
    """Apply deterministic redaction rules and return sanitized text plus counts."""

    def __init__(self, rules: Iterable[RedactionRule]) -> None:
        self._rules = tuple(rules)

    @classmethod
    def from_security_config(
        cls,
        config: SecurityConfig | None,
        *,
        pii_required: bool,
    ) -> Redactor:
        rules = [*builtin_rules(pii_required=pii_required)]
        if config is not None:
            rules.extend(configured_rules(config.redaction_rules))
        return cls(rules)

    def redact(
        self, text: str | None
    ) -> tuple[str | None, tuple[RedactionFinding, ...]]:
        if text is None:
            return None, ()

        sanitized = text
        sequence_by_type: dict[str, int] = {}
        findings: list[RedactionFinding] = []
        for rule in self._rules:
            matches = list(rule.pattern.finditer(sanitized))
            if not matches:
                continue

            redaction_type = rule.redaction_type
            sequence_by_type[redaction_type] = (
                sequence_by_type.get(redaction_type, 0) + 1
            )
            sequence = sequence_by_type[redaction_type]
            marker = f"[REDACTED:{redaction_type.upper()}:{sequence}]"
            sanitized = rule.pattern.sub(marker, sanitized)
            findings.append(
                RedactionFinding(
                    rule_id=rule.rule_id,
                    redaction_type=redaction_type,
                    marker=marker,
                    count=len(matches),
                    confidence=0.95,
                    scanner_name=rule.scanner_name,
                    scanner_version=rule.scanner_version,
                    severity=rule.severity,
                )
            )
        return sanitized, tuple(findings)


def builtin_rules(*, pii_required: bool) -> tuple[RedactionRule, ...]:
    """Return local deterministic rules that do not require external services."""

    rules = [
        RedactionRule(
            rule_id="builtin-api-key-assignment",
            redaction_type="secret",
            severity="high",
            pattern=re.compile(
                r"(?i)\b(?:api[_-]?key|token|secret|password|credential)\b"
                r"\s*(?:is|=|:)\s*['\"]?[^'\"\s,;]+"
            ),
        ),
        RedactionRule(
            rule_id="builtin-bearer-token",
            redaction_type="secret",
            severity="high",
            pattern=re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
        ),
        RedactionRule(
            rule_id="builtin-private-key-block",
            redaction_type="secret",
            severity="critical",
            pattern=re.compile(
                r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?"
                r"-----END [A-Z ]+ PRIVATE KEY-----",
                re.DOTALL,
            ),
        ),
        RedactionRule(
            rule_id="builtin-connection-string",
            redaction_type="secret",
            severity="high",
            pattern=re.compile(
                r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb|redis)://[^\s'\"<>]+"
            ),
        ),
        RedactionRule(
            rule_id="builtin-cloud-access-key",
            redaction_type="secret",
            severity="high",
            pattern=re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        ),
    ]
    if pii_required:
        rules.append(
            RedactionRule(
                rule_id="builtin-email-address",
                redaction_type="pii",
                severity="medium",
                pattern=re.compile(
                    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
                    re.IGNORECASE,
                ),
            )
        )
    return tuple(rules)


def configured_rules(
    config_rules: Iterable[RedactionRuleConfig],
) -> tuple[RedactionRule, ...]:
    """Compile enabled regex rules from security config."""

    rules: list[RedactionRule] = []
    for rule in config_rules:
        if not rule.enabled or not rule.pattern:
            continue
        rules.append(
            RedactionRule(
                rule_id=rule.rule_id,
                redaction_type=_configured_redaction_type(rule.marker),
                severity=rule.severity,
                pattern=re.compile(rule.pattern, re.MULTILINE | re.DOTALL),
                scanner_name=rule.detector,
                scanner_version="config",
            )
        )
    return tuple(rules)


def _configured_redaction_type(marker: str) -> str:
    marker_lower = marker.lower()
    if "pii" in marker_lower or "email" in marker_lower:
        return "pii"
    return "secret"
