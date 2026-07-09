"""Contracts and shared helpers for sanitized chunking."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.extractors import LineRange
from idp_brain.ingestion.extractors.base import safe_content_hash
from idp_brain.ingestion.redaction_stage import (
    SAFE_REDACTION_STATUSES,
    SanitizedExtractionCandidate,
    UnredactedCandidateError,
    assert_candidate_redacted,
)
from idp_brain.ingestion.runs import sanitize_diagnostic_text

CHUNKING_SCHEMA_VERSION = "sanitized-chunks-v1"
DEFAULT_CHUNK_SIZE_CHARS = 1200
DEFAULT_CHUNK_OVERLAP_CHARS = 120


@dataclass(frozen=True)
class ChunkingSettings:
    """Deterministic chunk size settings loaded from extractor profile options."""

    chunk_size_chars: int = DEFAULT_CHUNK_SIZE_CHARS
    chunk_overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS

    @classmethod
    def from_profile(cls, profile: ExtractorProfileConfig | None) -> ChunkingSettings:
        if profile is None:
            return cls()
        for tool in profile.tools:
            if not tool.enabled:
                continue
            chunk_size = _int_option(tool.options.get("chunk_size_chars"))
            overlap = _int_option(tool.options.get("chunk_overlap_chars"))
            if chunk_size is not None or overlap is not None:
                return cls(
                    chunk_size_chars=max(1, chunk_size or DEFAULT_CHUNK_SIZE_CHARS),
                    chunk_overlap_chars=max(0, overlap or DEFAULT_CHUNK_OVERLAP_CHARS),
                )
        return cls()


@dataclass(frozen=True)
class SanitizedCitation:
    """Persistence-ready citation metadata for one sanitized chunk."""

    citation_key: str
    source_url: str
    source_id: str
    source_version_id: str | None
    artifact_id: str
    line_range: LineRange | None
    source_type: str
    sanitized_content_hash: str
    redaction_status: str
    source_allowlisted: bool
    visibility_label: str
    sensitivity_class: str
    corpus_eligibility_label: str
    license_policy_label: str
    license_id: str | None


@dataclass(frozen=True)
class SanitizedChunk:
    """Persistence-ready sanitized chunk with safe structure/provenance metadata."""

    chunk_key: str
    artifact_id: str
    extraction_id: str | None
    source_id: str
    source_version_id: str | None
    source_type: str
    source_url: str
    artifact_path: str
    logical_locator: str
    sanitized_text: str
    sanitized_content_hash: str
    heading_path: str | None
    structure_path: tuple[str, ...]
    symbol_path: str | None
    signature_text: str | None
    language: str | None
    artifact_role: str | None
    chunk_kind: str
    chunker_profile: str
    token_count: int
    redaction_status: str
    source_allowlisted: bool
    visibility_label: str
    sensitivity_class: str
    corpus_eligibility_label: str
    license_policy_label: str
    license_id: str | None
    line_range: LineRange | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkingResult:
    """Chunker output for a single sanitized extraction candidate."""

    chunks: tuple[SanitizedChunk, ...]
    citations: tuple[SanitizedCitation, ...]


@runtime_checkable
class Chunker(Protocol):
    """Convert sanitized extraction candidates into chunks and citations."""

    profile: str

    def chunk(
        self,
        candidate: SanitizedExtractionCandidate,
        *,
        extraction_id: str | None = None,
    ) -> ChunkingResult:
        """Return deterministic sanitized chunks for one safe candidate."""


def build_chunks_for_candidate(
    *,
    candidate: SanitizedExtractionCandidate,
    chunk_kind: str,
    chunker_profile: str,
    settings: ChunkingSettings,
    extraction_id: str | None,
    structure_path: tuple[str, ...],
    heading_path: tuple[str, ...] = (),
    symbol_path: tuple[str, ...] = (),
    signature_text: str | None = None,
    language: str | None = None,
    metadata: dict[str, object] | None = None,
) -> ChunkingResult:
    """Build bounded chunks and citations for a redacted candidate."""

    assert_candidate_redacted(candidate)
    if candidate.sanitized_text is None or not candidate.sanitized_text.strip():
        return ChunkingResult(chunks=(), citations=())
    if candidate.redaction_status not in SAFE_REDACTION_STATUSES:
        raise UnredactedCandidateError(
            "candidate must be redacted or redaction_checked before chunking"
        )

    original = candidate.original
    source_id = original.source_id or "unknown"
    artifact_id = original.artifact_id or "unknown"
    source_type = original.source_type or "unknown"
    artifact_path = _required_text(
        original.metadata.get("artifact_path"),
        original.locator,
    )
    safe_locator = sanitize_diagnostic_text(original.locator)
    db_redaction_status = "redacted"
    parts = tuple(_split_text(candidate.sanitized_text, settings))
    chunks: list[SanitizedChunk] = []
    citations: list[SanitizedCitation] = []
    for ordinal, text in enumerate(parts):
        content_hash = safe_content_hash(text)
        chunk_key = stable_chunk_key(
            source_id=source_id,
            artifact_locator=original.locator,
            sanitized_content_hash=content_hash,
            chunker_profile=chunker_profile,
            structure_path=structure_path,
            ordinal=ordinal,
        )
        citation_key = stable_citation_key(chunk_key)
        chunk = SanitizedChunk(
            chunk_key=chunk_key,
            artifact_id=artifact_id,
            extraction_id=extraction_id,
            source_id=source_id,
            source_version_id=original.source_version_id,
            source_type=source_type,
            source_url=safe_locator,
            artifact_path=artifact_path,
            logical_locator=safe_locator,
            sanitized_text=text,
            sanitized_content_hash=content_hash,
            heading_path=" > ".join(heading_path) if heading_path else None,
            structure_path=structure_path,
            symbol_path=".".join(symbol_path) if symbol_path else None,
            signature_text=signature_text,
            language=language or original.language,
            artifact_role=_string_or_none(original.metadata.get("artifact_role")),
            chunk_kind=chunk_kind,
            chunker_profile=chunker_profile,
            token_count=_token_count(text),
            redaction_status=db_redaction_status,
            source_allowlisted=original.source_allowlisted,
            visibility_label=candidate.visibility_label,
            sensitivity_class=candidate.sensitivity_class,
            corpus_eligibility_label=candidate.corpus_eligibility_label,
            license_policy_label=candidate.license_policy_label,
            license_id=candidate.license_finding.license_id,
            line_range=original.line_range,
            metadata={
                "schema_version": CHUNKING_SCHEMA_VERSION,
                "candidate_type": original.candidate_type,
                "candidate_locator_hash": safe_content_hash(original.locator),
                "chunker_profile": chunker_profile,
                "structure_path": list(structure_path),
                **(metadata or {}),
            },
        )
        chunks.append(chunk)
        citations.append(
            SanitizedCitation(
                citation_key=citation_key,
                source_url=safe_locator,
                source_id=source_id,
                source_version_id=original.source_version_id,
                artifact_id=artifact_id,
                line_range=original.line_range,
                source_type=source_type,
                sanitized_content_hash=content_hash,
                redaction_status=db_redaction_status,
                source_allowlisted=original.source_allowlisted,
                visibility_label=candidate.visibility_label,
                sensitivity_class=candidate.sensitivity_class,
                corpus_eligibility_label=candidate.corpus_eligibility_label,
                license_policy_label=candidate.license_policy_label,
                license_id=candidate.license_finding.license_id,
            )
        )
    return ChunkingResult(chunks=tuple(chunks), citations=tuple(citations))


def stable_chunk_key(
    *,
    source_id: str,
    artifact_locator: str,
    sanitized_content_hash: str,
    chunker_profile: str,
    structure_path: tuple[str, ...],
    ordinal: int,
) -> str:
    payload = "\x1f".join(
        (
            source_id,
            artifact_locator,
            sanitized_content_hash,
            chunker_profile,
            "/".join(structure_path),
            str(ordinal),
        )
    )
    return f"chunk:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def stable_citation_key(chunk_key: str) -> str:
    return "citation:" + chunk_key.removeprefix("chunk:")


def _split_text(text: str, settings: ChunkingSettings) -> Iterable[str]:
    normalized = text.strip()
    if len(normalized) <= settings.chunk_size_chars:
        yield normalized
        return
    start = 0
    overlap = min(settings.chunk_overlap_chars, settings.chunk_size_chars - 1)
    while start < len(normalized):
        end = min(len(normalized), start + settings.chunk_size_chars)
        yield normalized[start:end].strip()
        if end == len(normalized):
            return
        start = end - overlap


def _token_count(text: str) -> int:
    return len(text.split())


def _int_option(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _required_text(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback
