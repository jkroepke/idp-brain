"""Shared contracts for untrusted artifact extraction output."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from idp_brain.ingestion.runs import sanitize_diagnostic_text

EXTRACTION_SCHEMA_VERSION = "extractor-candidates-v1"


@dataclass(frozen=True)
class LineRange:
    """One-based inclusive source line range when the parser can prove it."""

    start: int
    end: int

    @classmethod
    def from_zero_based(cls, line_map: list[int] | None) -> LineRange | None:
        if line_map is None or len(line_map) != 2:
            return None
        return cls(start=line_map[0] + 1, end=line_map[1])

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}


@dataclass(frozen=True)
class ArtifactExtractionContext:
    """Safe provenance copied from a discovered artifact."""

    artifact_id: str
    source_id: str
    source_version_id: str | None
    path: str
    logical_locator: str
    source_type: str
    artifact_role: str | None
    language: str | None
    extractor_profile: str | None
    visibility_label: str
    sensitivity_class: str
    license_policy_label: str
    corpus_eligibility_label: str
    source_allowlisted: bool = False


@dataclass(frozen=True)
class ExtractionCandidate:
    """Untrusted in-memory text or structure emitted for later redaction."""

    candidate_type: str
    text: str | None
    locator: str
    line_range: LineRange | None = None
    heading_path: tuple[str, ...] = ()
    key_path: tuple[str, ...] = ()
    schema_path: tuple[str, ...] = ()
    endpoint_path: str | None = None
    symbol_path: tuple[str, ...] = ()
    signature_text: str | None = None
    language: str | None = None
    source_id: str | None = None
    source_version_id: str | None = None
    artifact_id: str | None = None
    source_type: str | None = None
    source_allowlisted: bool = False
    visibility_label: str | None = None
    sensitivity_class: str | None = None
    license_policy_label: str | None = None
    corpus_eligibility_label: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def safe_metadata(self) -> dict[str, object]:
        """Return metadata suitable for diagnostics without raw candidate text."""

        payload: dict[str, object] = {
            "type": self.candidate_type,
            "locator": sanitize_diagnostic_text(self.locator),
        }
        if self.line_range is not None:
            payload["line_range"] = self.line_range.to_dict()
        if self.heading_path:
            payload["heading_path"] = [
                sanitize_diagnostic_text(v) for v in self.heading_path
            ]
        if self.key_path:
            payload["key_path"] = list(self.key_path)
        if self.schema_path:
            payload["schema_path"] = list(self.schema_path)
        if self.endpoint_path is not None:
            payload["endpoint_path"] = sanitize_diagnostic_text(self.endpoint_path)
        if self.symbol_path:
            payload["symbol_path"] = [
                sanitize_diagnostic_text(v) for v in self.symbol_path
            ]
        if self.signature_text is not None:
            payload["signature_hash"] = safe_content_hash(self.signature_text)
        if self.language is not None:
            payload["language"] = self.language
        if self.source_id is not None:
            payload["source_id"] = self.source_id
        if self.source_version_id is not None:
            payload["source_version_id"] = self.source_version_id
        if self.artifact_id is not None:
            payload["artifact_id"] = self.artifact_id
        if self.source_type is not None:
            payload["source_type"] = self.source_type
        payload["source_allowlisted"] = self.source_allowlisted
        if self.visibility_label is not None:
            payload["visibility_label"] = self.visibility_label
        if self.sensitivity_class is not None:
            payload["sensitivity_class"] = self.sensitivity_class
        if self.license_policy_label is not None:
            payload["license_policy_label"] = self.license_policy_label
        if self.corpus_eligibility_label is not None:
            payload["corpus_eligibility_label"] = self.corpus_eligibility_label
        return payload


@dataclass(frozen=True)
class ExtractionDiagnostic:
    """Sanitized parser diagnostic."""

    severity: str
    code: str
    message: str
    locator: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "severity": self.severity,
            "code": self.code,
            "message": sanitize_diagnostic_text(self.message),
        }
        if self.locator is not None:
            payload["locator"] = sanitize_diagnostic_text(self.locator)
        return payload


@dataclass(frozen=True)
class ExtractionResult:
    """In-memory extractor output for the redaction stage."""

    extractor_name: str
    extractor_version: str
    artifact: ArtifactExtractionContext
    candidates: tuple[ExtractionCandidate, ...]
    diagnostics: tuple[ExtractionDiagnostic, ...] = ()

    @property
    def status(self) -> str:
        if any(diagnostic.severity == "error" for diagnostic in self.diagnostics):
            return "failed"
        if not self.candidates:
            return "skipped"
        return "completed"

    def safe_summary(self) -> dict[str, object]:
        """Return a persistence-safe count summary without raw extracted text."""

        counts: dict[str, int] = {}
        for candidate in self.candidates:
            counts[candidate.candidate_type] = (
                counts.get(candidate.candidate_type, 0) + 1
            )
        return {
            "schema_version": EXTRACTION_SCHEMA_VERSION,
            "candidate_count": len(self.candidates),
            "candidate_counts": counts,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


@runtime_checkable
class Extractor(Protocol):
    """Parser contract for one artifact role/profile."""

    name: str
    version: str
    supported_artifact_roles: frozenset[str]

    def extract(
        self,
        artifact: ArtifactExtractionContext,
        stream: bytes,
    ) -> ExtractionResult:
        """Return untrusted candidates without executing or fetching anything."""


def decode_utf8(
    extractor_name: str,
    artifact: ArtifactExtractionContext,
    stream: bytes,
) -> tuple[str, tuple[ExtractionDiagnostic, ...]]:
    """Decode a parser input as UTF-8 and sanitize any decode diagnostics."""

    try:
        return stream.decode("utf-8"), ()
    except UnicodeDecodeError as exc:
        return (
            stream.decode("utf-8", errors="replace"),
            (
                ExtractionDiagnostic(
                    severity="warning",
                    code="decode_replacement",
                    message=(
                        f"{extractor_name} replaced undecodable bytes: {exc.reason}"
                    ),
                    locator=artifact.logical_locator,
                ),
            ),
        )


def scalar_summary(value: object) -> str:
    """Bounded string form for in-memory scalar candidates."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def safe_content_hash(value: str) -> str:
    """Non-reversible hash for parser metadata."""

    import hashlib

    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def result_with_parse_error(
    *,
    extractor_name: str,
    extractor_version: str,
    artifact: ArtifactExtractionContext,
    code: str,
    error: BaseException,
) -> ExtractionResult:
    """Build a failed extraction result with a sanitized parse diagnostic."""

    return ExtractionResult(
        extractor_name=extractor_name,
        extractor_version=extractor_version,
        artifact=artifact,
        candidates=(),
        diagnostics=(
            ExtractionDiagnostic(
                severity="error",
                code=code,
                message=str(error),
                locator=artifact.logical_locator,
            ),
        ),
    )


def make_result(
    *,
    extractor_name: str,
    extractor_version: str,
    artifact: ArtifactExtractionContext,
    candidates: Iterable[ExtractionCandidate],
    diagnostics: Iterable[ExtractionDiagnostic] = (),
) -> ExtractionResult:
    return ExtractionResult(
        extractor_name=extractor_name,
        extractor_version=extractor_version,
        artifact=artifact,
        candidates=tuple(
            _with_artifact_provenance(candidate, artifact) for candidate in candidates
        ),
        diagnostics=tuple(diagnostics),
    )


def _with_artifact_provenance(
    candidate: ExtractionCandidate,
    artifact: ArtifactExtractionContext,
) -> ExtractionCandidate:
    metadata = {
        **dict(candidate.metadata),
        "artifact_path": artifact.path,
        "artifact_role": artifact.artifact_role,
        "extractor_profile": artifact.extractor_profile,
    }
    return replace(
        candidate,
        source_id=artifact.source_id,
        source_version_id=artifact.source_version_id,
        artifact_id=artifact.artifact_id,
        source_type=artifact.source_type,
        source_allowlisted=artifact.source_allowlisted,
        visibility_label=artifact.visibility_label,
        sensitivity_class=artifact.sensitivity_class,
        license_policy_label=artifact.license_policy_label,
        corpus_eligibility_label=artifact.corpus_eligibility_label,
        metadata=metadata,
    )
